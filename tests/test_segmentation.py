"""
test_segmentation.py
Unit tests for the customer segmentation pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import pandas as pd
import numpy as np
from segmentation import get_rfm_data, run_segmentation, summarize_segments


class TestGetRFMData:
    def test_returns_dataframe(self):
        rfm = get_rfm_data()
        assert isinstance(rfm, pd.DataFrame)

    def test_has_required_columns(self):
        rfm = get_rfm_data()
        for col in ["user_id", "recency_days", "frequency", "monetary"]:
            assert col in rfm.columns, f"Missing column: {col}"

    def test_no_negative_values(self):
        rfm = get_rfm_data()
        assert (rfm["recency_days"] >= 0).all(), "Recency should be non-negative"
        assert (rfm["frequency"] > 0).all(), "Frequency should be positive"
        assert (rfm["monetary"] > 0).all(), "Monetary should be positive"

    def test_unique_users(self):
        rfm = get_rfm_data()
        assert rfm["user_id"].is_unique, "Each user should appear exactly once"


class TestRunSegmentation:
    def test_returns_correct_types(self):
        rfm, centroids, label_map = run_segmentation()
        assert isinstance(rfm, pd.DataFrame)
        assert isinstance(centroids, pd.DataFrame)
        assert isinstance(label_map, dict)

    def test_segment_column_added(self):
        rfm, _, _ = run_segmentation()
        assert "segment" in rfm.columns
        assert "cluster" in rfm.columns

    def test_all_users_assigned(self):
        rfm, _, _ = run_segmentation()
        assert rfm["segment"].notna().all(), "Every user should have a segment"

    def test_valid_segment_names(self):
        valid_names = {"High-Value Loyalists", "Growing Regulars",
                       "At-Risk / Dormant", "Low-Value / Occasional"}
        rfm, _, _ = run_segmentation()
        actual = set(rfm["segment"].unique())
        assert actual.issubset(valid_names), f"Unexpected segments: {actual - valid_names}"

    def test_custom_cluster_count(self):
        rfm, _, label_map = run_segmentation(n_clusters=3)
        assert len(label_map) == 3


class TestSummarizeSegments:
    def test_summary_columns(self):
        rfm, _, _ = run_segmentation()
        summary = summarize_segments(rfm)
        expected_cols = ["users", "avg_recency_days", "avg_frequency",
                         "avg_monetary", "total_revenue", "pct_of_users", "pct_of_revenue"]
        for col in expected_cols:
            assert col in summary.columns, f"Missing summary column: {col}"

    def test_pct_of_users_sums_to_100(self):
        rfm, _, _ = run_segmentation()
        summary = summarize_segments(rfm)
        assert abs(summary["pct_of_users"].sum() - 100) < 1, "pct_of_users should sum to ~100"

    def test_pct_of_revenue_sums_to_100(self):
        rfm, _, _ = run_segmentation()
        summary = summarize_segments(rfm)
        assert abs(summary["pct_of_revenue"].sum() - 100) < 1, "pct_of_revenue should sum to ~100"

    def test_sorted_by_revenue(self):
        rfm, _, _ = run_segmentation()
        summary = summarize_segments(rfm)
        revenues = summary["total_revenue"].values
        assert all(revenues[i] >= revenues[i+1] for i in range(len(revenues)-1))
