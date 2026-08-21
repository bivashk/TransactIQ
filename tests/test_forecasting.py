"""
test_forecasting.py
Unit tests for the revenue forecasting pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import pandas as pd
import numpy as np
from forecasting import get_monthly_revenue, forecast_revenue


class TestGetMonthlyRevenue:
    def test_returns_dataframe(self):
        df = get_monthly_revenue()
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = get_monthly_revenue()
        for col in ["month", "revenue", "txn_count"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_months_are_sorted(self):
        df = get_monthly_revenue()
        months = df["month"].tolist()
        assert months == sorted(months), "Months should be in chronological order"

    def test_positive_revenue(self):
        df = get_monthly_revenue()
        assert (df["revenue"] > 0).all(), "Revenue should be positive"

    def test_twelve_months(self):
        df = get_monthly_revenue()
        assert len(df) == 12, f"Expected 12 months, got {len(df)}"


class TestForecastRevenue:
    @pytest.fixture
    def historical(self):
        return get_monthly_revenue()

    def test_returns_correct_tuple(self, historical):
        forecast, model, growth_rate = forecast_revenue(historical)
        assert isinstance(forecast, pd.DataFrame)
        assert isinstance(growth_rate, (float, np.floating))

    def test_forecast_has_correct_columns(self, historical):
        forecast, _, _ = forecast_revenue(historical)
        for col in ["month", "forecast_revenue", "lower_bound", "upper_bound"]:
            assert col in forecast.columns, f"Missing column: {col}"

    def test_forecast_length(self, historical):
        forecast, _, _ = forecast_revenue(historical, months_ahead=3)
        assert len(forecast) == 3

    def test_custom_forecast_length(self, historical):
        forecast, _, _ = forecast_revenue(historical, months_ahead=6)
        assert len(forecast) == 6

    def test_confidence_bounds(self, historical):
        forecast, _, _ = forecast_revenue(historical)
        assert (forecast["lower_bound"] < forecast["forecast_revenue"]).all()
        assert (forecast["upper_bound"] > forecast["forecast_revenue"]).all()

    def test_growth_rate_is_reasonable(self, historical):
        _, _, growth_rate = forecast_revenue(historical)
        assert -100 < growth_rate < 500, f"Growth rate {growth_rate}% seems unreasonable"

    def test_forecast_months_are_future(self, historical):
        forecast, _, _ = forecast_revenue(historical)
        last_historical = historical["month"].iloc[-1]
        assert all(m > last_historical for m in forecast["month"])
