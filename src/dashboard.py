"""
dashboard.py
Interactive Streamlit dashboard for TransactIQ. Surfaces the key
business metrics, customer segments, and revenue forecast in one view.
Run with: streamlit run src/dashboard.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

from segmentation import run_segmentation, summarize_segments
from forecasting import get_monthly_revenue, forecast_revenue

DB_PATH = "transactiq.db"

st.set_page_config(page_title="TransactIQ | Payments Analytics", layout="wide")
st.title("TransactIQ — Digital Payments Analytics Dashboard")
st.caption("SQL-driven analytics, customer segmentation & revenue forecasting on transaction data")


@st.cache_data
def load_kpis():
    conn = sqlite3.connect(DB_PATH)
    total_revenue = pd.read_sql_query(
        "SELECT SUM(amount) as v FROM transactions WHERE status='SUCCESS'", conn).iloc[0]["v"]
    total_txns = pd.read_sql_query("SELECT COUNT(*) as v FROM transactions", conn).iloc[0]["v"]
    total_users = pd.read_sql_query("SELECT COUNT(*) as v FROM users", conn).iloc[0]["v"]
    failure_rate = pd.read_sql_query(
        "SELECT 100.0*SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END)/COUNT(*) as v FROM transactions", conn
    ).iloc[0]["v"]
    conn.close()
    return total_revenue, total_txns, total_users, failure_rate


total_revenue, total_txns, total_users, failure_rate = load_kpis()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"₹{total_revenue/1e7:.2f} Cr")
c2.metric("Total Transactions", f"{total_txns:,}")
c3.metric("Registered Users", f"{total_users:,}")
c4.metric("Failure Rate", f"{failure_rate:.2f}%")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Monthly Revenue Trend & Forecast")
    historical = get_monthly_revenue()
    forecast, _, growth_rate = forecast_revenue(historical)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(historical["month"], historical["revenue"], marker="o", color="#5F259F", label="Actual")
    ax.plot(forecast["month"], forecast["forecast_revenue"], marker="o", linestyle="--", color="#00B9F1", label="Forecast")
    ax.set_xticklabels(list(historical["month"]) + list(forecast["month"]), rotation=45, fontsize=7)
    ax.legend()
    st.pyplot(fig)
    st.info(f"Projected revenue growth over next 3 months: **{growth_rate:.1f}%**")

with col2:
    st.subheader("Customer Segments (RFM + K-Means)")
    rfm, centroids, label_map = run_segmentation()
    summary = summarize_segments(rfm)
    st.dataframe(summary.style.format({
        "avg_recency_days": "{:.1f}", "avg_frequency": "{:.1f}",
        "avg_monetary": "₹{:.0f}", "total_revenue": "₹{:.0f}",
        "pct_of_users": "{:.1f}%", "pct_of_revenue": "{:.1f}%"
    }))
    st.caption("**Insight:** High-Value Loyalists are ~6% of users but drive ~36% of revenue — "
               "a strong candidate segment for a loyalty/rewards program.")

st.divider()

st.subheader("Category-wise Revenue Contribution")
conn = sqlite3.connect(DB_PATH)
cat_df = pd.read_sql_query("""
    SELECT category, SUM(amount) as revenue, COUNT(*) as txns
    FROM transactions WHERE status='SUCCESS'
    GROUP BY category ORDER BY revenue DESC
""", conn)
conn.close()
st.bar_chart(cat_df.set_index("category")["revenue"])

st.divider()
st.caption("Built with Python, SQL (SQLite/PostgreSQL-compatible), scikit-learn, and Streamlit.")
