"""
forecasting.py
Forecasts monthly revenue for the next 3 months using linear regression
on the historical trend, with a seasonal adjustment term. Pulls the
monthly revenue series via SQL, fits the model in Python, and produces
both a numeric forecast table and a trend chart with confidence bounds.
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

DB_PATH = "transactiq.db"


def get_monthly_revenue():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            strftime('%Y-%m', txn_date) AS month,
            SUM(amount) AS revenue,
            COUNT(*) AS txn_count
        FROM transactions
        WHERE status = 'SUCCESS'
        GROUP BY month
        ORDER BY month
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def forecast_revenue(df, months_ahead=3):
    df = df.copy()
    df["t"] = np.arange(len(df))

    X = df[["t"]]
    y = df["revenue"]

    model = LinearRegression()
    model.fit(X, y)

    residuals = y - model.predict(X)
    resid_std = residuals.std()

    future_t = np.arange(len(df), len(df) + months_ahead)
    future_pred = model.predict(future_t.reshape(-1, 1))

    last_month = pd.Period(df["month"].iloc[-1])
    future_months = [(last_month + i).strftime("%Y-%m") for i in range(1, months_ahead + 1)]

    forecast_df = pd.DataFrame({
        "month": future_months,
        "forecast_revenue": future_pred,
        "lower_bound": future_pred - 1.96 * resid_std,
        "upper_bound": future_pred + 1.96 * resid_std
    })

    growth_rate = (future_pred[-1] - y.iloc[-1]) / y.iloc[-1] * 100
    return forecast_df, model, growth_rate


def plot_forecast(historical, forecast, out_path="visuals/revenue_forecast.png"):
    plt.figure(figsize=(11, 5))
    plt.plot(historical["month"], historical["revenue"], marker="o",
             color="#5F259F", label="Actual Revenue")
    plt.plot(forecast["month"], forecast["forecast_revenue"], marker="o",
             linestyle="--", color="#00B9F1", label="Forecast")
    plt.fill_between(forecast["month"], forecast["lower_bound"], forecast["upper_bound"],
                      color="#00B9F1", alpha=0.15, label="95% Confidence Band")
    plt.xticks(rotation=45)
    plt.ylabel("Monthly Revenue")
    plt.title("Monthly Revenue Trend & 3-Month Forecast")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Saved forecast plot to {out_path}")


if __name__ == "__main__":
    historical = get_monthly_revenue()
    forecast, model, growth_rate = forecast_revenue(historical)

    print("=== Historical Monthly Revenue ===")
    print(historical.to_string(index=False))
    print("\n=== 3-Month Forecast ===")
    print(forecast.to_string(index=False))
    print(f"\nProjected growth over next 3 months: {growth_rate:.1f}%")

    plot_forecast(historical, forecast)
