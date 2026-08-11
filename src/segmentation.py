"""
segmentation.py
Customer segmentation using RFM (Recency, Frequency, Monetary) analysis
and K-Means clustering. Pulls RFM base metrics via SQL, then applies
scaling + clustering in Python, and labels clusters with business-
readable segment names based on their centroid characteristics.
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

DB_PATH = "transactiq.db"


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
    rfm, centroids, label_map = run_segmentation()
    summary = summarize_segments(rfm)

    print("=== Segment Summary ===")
    print(summary.to_string())

    plot_segments(rfm)
    rfm.to_csv("data/customer_segments.csv", index=False)
    print("\nSaved per-user segment assignments to data/customer_segments.csv")
