"""
forecasting.py
Forecasts monthly revenue for the next 3 months using linear regression
on the historical trend, with a seasonal adjustment term. Pulls the
monthly revenue series via SQL, fits the model in Python, and produces
both a numeric forecast table and a trend chart with confidence bounds.
"""

import os
import sqlite3
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_squared_error
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "transactiq.db")


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


def forecast_revenue_seasonal(df, months_ahead=3):
    df = df.copy()
    df["t"] = np.arange(len(df))
    df["sin_t"] = np.sin(2 * np.pi * df["t"] / 12)
    df["cos_t"] = np.cos(2 * np.pi * df["t"] / 12)

    X = df[["t", "sin_t", "cos_t"]]
    y = df["revenue"]

    model = LinearRegression()
    model.fit(X, y)

    residuals = y - model.predict(X)
    resid_std = residuals.std()

    future_t = np.arange(len(df), len(df) + months_ahead)
    future_sin = np.sin(2 * np.pi * future_t / 12)
    future_cos = np.cos(2 * np.pi * future_t / 12)
    future_X = pd.DataFrame({
        "t": future_t,
        "sin_t": future_sin,
        "cos_t": future_cos
    })
    future_pred = model.predict(future_X)

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


def compare_models(df):
    df = df.copy()
    y = df["revenue"]

    _, model_lin, _ = forecast_revenue(df)
    t = np.arange(len(df))
    X_lin = pd.DataFrame({"t": t})
    y_pred_lin = model_lin.predict(X_lin)
    r2_lin = r2_score(y, y_pred_lin)
    rmse_lin = float(np.sqrt(mean_squared_error(y, y_pred_lin)))

    _, model_seas, _ = forecast_revenue_seasonal(df)
    X_seas = pd.DataFrame({
        "t": t,
        "sin_t": np.sin(2 * np.pi * t / 12),
        "cos_t": np.cos(2 * np.pi * t / 12)
    })
    y_pred_seas = model_seas.predict(X_seas)
    r2_seas = r2_score(y, y_pred_seas)
    rmse_seas = float(np.sqrt(mean_squared_error(y, y_pred_seas)))

    return pd.DataFrame({
        "model": ["Linear", "Seasonal"],
        "r2": [r2_lin, r2_seas],
        "rmse": [rmse_lin, rmse_seas]
    })


def plot_forecast(historical, forecast, seasonal_forecast=None, out_path="visuals/revenue_forecast.png"):
    plt.figure(figsize=(11, 5))
    plt.plot(historical["month"], historical["revenue"], marker="o",
             color="#5F259F", label="Actual Revenue")
    plt.plot(forecast["month"], forecast["forecast_revenue"], marker="o",
             linestyle="--", color="#00B9F1", label="Forecast")
    plt.fill_between(forecast["month"], forecast["lower_bound"], forecast["upper_bound"],
                      color="#00B9F1", alpha=0.15, label="95% Confidence Band")

    if seasonal_forecast is not None:
        plt.plot(seasonal_forecast["month"], seasonal_forecast["forecast_revenue"], marker="o",
                 linestyle="--", color="#FF6B6B", label="Seasonal Forecast")
        plt.fill_between(seasonal_forecast["month"], seasonal_forecast["lower_bound"], seasonal_forecast["upper_bound"],
                          color="#FF6B6B", alpha=0.15, label="Seasonal 95% Confidence Band")

    plt.xticks(rotation=45)
    plt.ylabel("Monthly Revenue")
    plt.title("Monthly Revenue Trend & 3-Month Forecast")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"Saved forecast plot to {out_path}")


if __name__ == "__main__":
    historical = get_monthly_revenue()

    print("=== Historical Monthly Revenue ===")
    print(historical.to_string(index=False))

    print("\n=== Model Comparison ===")
    comparison = compare_models(historical)
    print(comparison.to_string(index=False))

    forecast, model, growth_rate = forecast_revenue(historical)
    seasonal_forecast, seasonal_model, seasonal_growth_rate = forecast_revenue_seasonal(historical)

    print("\n=== 3-Month Forecast (Linear) ===")
    print(forecast.to_string(index=False))
    print(f"\nProjected growth over next 3 months (Linear): {growth_rate:.1f}%")

    print("\n=== 3-Month Forecast (Seasonal) ===")
    print(seasonal_forecast.to_string(index=False))
    print(f"\nProjected growth over next 3 months (Seasonal): {seasonal_growth_rate:.1f}%")

    plot_forecast(historical, forecast, seasonal_forecast=seasonal_forecast)
