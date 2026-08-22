"""
segmentation.py
Customer segmentation using RFM (Recency, Frequency, Monetary) analysis
and K-Means clustering. Pulls RFM base metrics via SQL, then applies
scaling + clustering in Python, and labels clusters with business-
readable segment names based on their centroid characteristics.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "transactiq.db")


def get_rfm_data():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            user_id,
            JULIANDAY((SELECT MAX(txn_date) FROM transactions)) - JULIANDAY(MAX(txn_date)) AS recency_days,
            COUNT(*) AS frequency,
            SUM(amount) AS monetary
        FROM transactions
        WHERE status = 'SUCCESS'
        GROUP BY user_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def evaluate_cluster_count(k_min=2, k_max=8):
    rfm = get_rfm_data()
    features = rfm[["recency_days", "frequency", "monetary"]]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)

    results = []
    for k in range(k_min, k_max + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(scaled)
        results.append({
            "k": k,
            "inertia": kmeans.inertia_,
            "silhouette_score": silhouette_score(scaled, labels)
        })

    return pd.DataFrame(results)


def plot_elbow_silhouette(eval_df, out_path="visuals/elbow_silhouette.png"):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    primary_color = "#5F259F"

    # Left panel: Inertia vs k (Elbow Method)
    axes[0].plot(eval_df["k"], eval_df["inertia"], marker="o", color=primary_color, linewidth=2)
    axes[0].set_xlabel("Number of Clusters (k)")
    axes[0].set_ylabel("Inertia")
    axes[0].set_title("Elbow Method: Inertia vs k")
    axes[0].set_xticks(eval_df["k"])
    axes[0].grid(True, linestyle="--", alpha=0.5)

    # Right panel: Silhouette Score vs k
    axes[1].plot(eval_df["k"], eval_df["silhouette_score"], marker="o", color=primary_color, linewidth=2)
    axes[1].set_xlabel("Number of Clusters (k)")
    axes[1].set_ylabel("Silhouette Score")
    axes[1].set_title("Silhouette Score vs k")
    axes[1].set_xticks(eval_df["k"])
    axes[1].grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Saved elbow and silhouette plot to {out_path}")


def run_segmentation(n_clusters=4):
    rfm = get_rfm_data()

    features = rfm[["recency_days", "frequency", "monetary"]]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    rfm["cluster"] = kmeans.fit_predict(scaled)

    # Label clusters by business meaning using explicit RFM rules on centroids,
    # rather than a single composite score — recency needs its own threshold
    # since "recent but low-spend" and "high-spend but gone quiet" are very
    # different segments even if a blended score would rank them similarly.
    centroids = rfm.groupby("cluster")[["recency_days", "frequency", "monetary"]].mean()
    median_recency = centroids["recency_days"].median()
    value_rank = (centroids["frequency"].rank() + centroids["monetary"].rank())

    label_map = {}
    for cluster_id, row in centroids.iterrows():
        is_stale = row["recency_days"] > median_recency and row["recency_days"] > 30
        is_top_value = value_rank[cluster_id] == value_rank.max()
        is_bottom_value = value_rank[cluster_id] == value_rank.min()

        if is_stale:
            label_map[cluster_id] = "At-Risk / Dormant"
        elif is_top_value:
            label_map[cluster_id] = "High-Value Loyalists"
        elif is_bottom_value:
            label_map[cluster_id] = "Low-Value / Occasional"
        else:
            label_map[cluster_id] = "Growing Regulars"

    rfm["segment"] = rfm["cluster"].map(label_map)

    return rfm, centroids, label_map


def summarize_segments(rfm):
    summary = rfm.groupby("segment").agg(
        users=("user_id", "count"),
        avg_recency_days=("recency_days", "mean"),
        avg_frequency=("frequency", "mean"),
        avg_monetary=("monetary", "mean"),
        total_revenue=("monetary", "sum")
    ).sort_values("total_revenue", ascending=False)
    summary["pct_of_users"] = round(100 * summary["users"] / summary["users"].sum(), 1)
    summary["pct_of_revenue"] = round(100 * summary["total_revenue"] / summary["total_revenue"].sum(), 1)
    return summary


def plot_segments(rfm, out_path="visuals/customer_segments.png"):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    colors = {"High-Value Loyalists": "#5F259F", "Growing Regulars": "#00B9F1",
              "At-Risk / Dormant": "#FF6B6B", "Low-Value / Occasional": "#B0B0B0"}

    for seg, group in rfm.groupby("segment"):
        axes[0].scatter(group["frequency"], group["monetary"],
                         label=seg, alpha=0.5, s=15, color=colors.get(seg))
    axes[0].set_xlabel("Frequency (transaction count)")
    axes[0].set_ylabel("Monetary (total spend)")
    axes[0].set_title("Customer Segments: Frequency vs Monetary")
    axes[0].legend(fontsize=8)

    seg_counts = rfm["segment"].value_counts()
    axes[1].pie(seg_counts, labels=seg_counts.index, autopct="%1.1f%%",
                colors=[colors.get(s) for s in seg_counts.index])
    axes[1].set_title("Segment Distribution (% of users)")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Saved segmentation plot to {out_path}")


if __name__ == "__main__":
    print("=== Evaluating Optimal Cluster Count (k=2..8) ===")
    eval_df = evaluate_cluster_count()
    print(eval_df.to_string(index=False))
    plot_elbow_silhouette(eval_df)

    rfm, centroids, label_map = run_segmentation()
    summary = summarize_segments(rfm)

    print("\n=== Segment Summary ===")
    print(summary.to_string())

    plot_segments(rfm)
    rfm.to_csv("data/customer_segments.csv", index=False)
    print("\nSaved per-user segment assignments to data/customer_segments.csv")
