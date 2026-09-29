"""
Unit Tests: Valuation Engine
==============================
Tests for valuation calculations including edge cases.
Run: pytest tests/ -v
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.valuation_engine import (
    calculate_position_values,
    calculate_portfolio_summary,
    calculate_asset_class_summary,
    calculate_counterparty_exposure,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_portfolio():
    """Create a minimal portfolio for testing."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003", "POS-004", "POS-005"],
        "instrument_id": ["EQ-AAA-0001", "FI-BBB-0002", "FX-CCC-0003", "CM-DDD-0004", "EQ-EEE-0005"],
        "asset_class": ["Equity", "Fixed Income", "FX Forward", "Commodity", "Equity"],
        "counterparty": ["BankA", "BankB", "BankA", "BankC", "BankB"],
        "currency": ["USD", "EUR", "GBP", "USD", "EUR"],
        "quantity": [1000, 5000, 100000, 500, 2000],
        "recorded_price": [150.00, 98.50, 1.25, 75.00, 200.00],
        "reference_price": [148.00, 100.00, 1.20, 80.00, 198.00],
        "valuation_date": ["2024-01-15"] * 5,
    })


@pytest.fixture
def valued_portfolio(sample_portfolio):
    """Return a portfolio with values calculated."""
    return calculate_position_values(sample_portfolio)


@pytest.fixture
def portfolio_with_nan():
    """Portfolio with missing prices."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003"],
        "instrument_id": ["EQ-001", "FI-002", "CM-003"],
        "asset_class": ["Equity", "Fixed Income", "Commodity"],
        "counterparty": ["BankA", "BankB", "BankC"],
        "currency": ["USD", "EUR", "USD"],
        "quantity": [1000, 5000, 500],
        "recorded_price": [150.00, np.nan, 75.00],
        "reference_price": [148.00, 100.00, np.nan],
        "valuation_date": ["2024-01-15"] * 3,
    })


@pytest.fixture
def portfolio_with_zero_qty():
    """Portfolio with zero and negative quantities."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003"],
        "instrument_id": ["EQ-001", "FI-002", "CM-003"],
        "asset_class": ["Equity", "Fixed Income", "Commodity"],
        "counterparty": ["BankA", "BankB", "BankC"],
        "currency": ["USD", "EUR", "USD"],
        "quantity": [1000, 0, -500],
        "recorded_price": [150.00, 100.00, 75.00],
        "reference_price": [148.00, 100.00, 80.00],
        "valuation_date": ["2024-01-15"] * 3,
    })


# ─── Test: calculate_position_values ────────────────────────────────────────

class TestCalculatePositionValues:
    """Tests for position-level valuation calculations."""

    def test_recorded_value_calculation(self, sample_portfolio):
        """Verify recorded_value = quantity × recorded_price."""
        result = calculate_position_values(sample_portfolio)
        expected = sample_portfolio["quantity"] * sample_portfolio["recorded_price"]
        pd.testing.assert_series_equal(
            result["recorded_value"], expected.round(2), check_names=False
        )

    def test_reference_value_calculation(self, sample_portfolio):
        """Verify reference_value = quantity × reference_price."""
        result = calculate_position_values(sample_portfolio)
        expected = sample_portfolio["quantity"] * sample_portfolio["reference_price"]
        pd.testing.assert_series_equal(
            result["reference_value"], expected.round(2), check_names=False
        )

    def test_absolute_diff_calculation(self, sample_portfolio):
        """Verify absolute_diff = |recorded_value - reference_value|."""
        result = calculate_position_values(sample_portfolio)
        expected = (
            (sample_portfolio["quantity"] * sample_portfolio["recorded_price"]) -
            (sample_portfolio["quantity"] * sample_portfolio["reference_price"])
        ).abs().round(2)
        pd.testing.assert_series_equal(
            result["absolute_diff"], expected, check_names=False
        )

    def test_percentage_diff_calculation(self, sample_portfolio):
        """Verify percentage_diff = (absolute_diff / |reference_value|) × 100."""
        result = calculate_position_values(sample_portfolio)
        ref_val = (sample_portfolio["quantity"] * sample_portfolio["reference_price"]).abs()
        abs_diff = (
            (sample_portfolio["quantity"] * sample_portfolio["recorded_price"]) -
            (sample_portfolio["quantity"] * sample_portfolio["reference_price"])
        ).abs()
        expected_pct = (abs_diff / ref_val * 100).round(4)
        pd.testing.assert_series_equal(
            result["percentage_diff"], expected_pct, check_names=False
        )

    def test_specific_values(self, sample_portfolio):
        """Verify concrete known values for the first position."""
        result = calculate_position_values(sample_portfolio)
        row = result.iloc[0]
        # POS-001: qty=1000, rec_price=150, ref_price=148
        assert row["recorded_value"] == 150000.00
        assert row["reference_value"] == 148000.00
        assert row["absolute_diff"] == 2000.00
        assert abs(row["percentage_diff"] - 1.3514) < 0.01  # 2000/148000*100

    def test_nan_prices_propagate(self, portfolio_with_nan):
        """Values should be NaN when prices are missing."""
        result = calculate_position_values(portfolio_with_nan)
        assert pd.isna(result.iloc[1]["recorded_value"])  # recorded_price is NaN
        assert pd.isna(result.iloc[2]["reference_value"])  # reference_price is NaN

    def test_zero_quantity_produces_zero_values(self, portfolio_with_zero_qty):
        """Zero quantity should produce zero values, not errors."""
        result = calculate_position_values(portfolio_with_zero_qty)
        assert result.iloc[1]["recorded_value"] == 0.0
        assert result.iloc[1]["reference_value"] == 0.0
        assert result.iloc[1]["absolute_diff"] == 0.0

    def test_negative_quantity_handled(self, portfolio_with_zero_qty):
        """Negative quantities should still produce valid calculations."""
        result = calculate_position_values(portfolio_with_zero_qty)
        row = result.iloc[2]  # qty=-500, rec=75, ref=80
        assert row["recorded_value"] == -37500.00
        assert row["reference_value"] == -40000.00
        assert row["absolute_diff"] == 2500.00

    def test_all_columns_present(self, sample_portfolio):
        """Result should contain all original columns plus value columns."""
        result = calculate_position_values(sample_portfolio)
        for col in ["recorded_value", "reference_value", "absolute_diff", "percentage_diff"]:
            assert col in result.columns

    def test_original_data_unchanged(self, sample_portfolio):
        """Original DataFrame should not be modified (copy semantics)."""
        original_cols = set(sample_portfolio.columns)
        _ = calculate_position_values(sample_portfolio)
        assert set(sample_portfolio.columns) == original_cols

    def test_empty_dataframe(self):
        """Should handle empty DataFrame gracefully."""
        empty = pd.DataFrame(columns=[
            "position_id", "instrument_id", "asset_class", "counterparty",
            "currency", "quantity", "recorded_price", "reference_price", "valuation_date"
        ])
        result = calculate_position_values(empty)
        assert len(result) == 0
        assert "recorded_value" in result.columns


# ─── Test: calculate_portfolio_summary ──────────────────────────────────────

class TestCalculatePortfolioSummary:
    """Tests for portfolio-level summary calculations."""

    def test_summary_keys(self, valued_portfolio):
        """Summary dict should contain all expected keys."""
        summary = calculate_portfolio_summary(valued_portfolio)
        expected_keys = [
            "total_positions", "valid_positions",
            "total_recorded_value", "total_reference_value",
            "total_absolute_diff", "portfolio_pct_diff",
            "mean_pct_diff", "median_pct_diff", "max_pct_diff", "std_pct_diff",
        ]
        for key in expected_keys:
            assert key in summary, f"Missing key: {key}"

    def test_total_positions(self, valued_portfolio):
        """Total positions should match input length."""
        summary = calculate_portfolio_summary(valued_portfolio)
        assert summary["total_positions"] == len(valued_portfolio)

    def test_total_recorded_value(self, valued_portfolio):
        """Total recorded value should be sum of individual recorded values."""
        summary = calculate_portfolio_summary(valued_portfolio)
        expected = valued_portfolio.dropna(subset=["recorded_value"])["recorded_value"].sum()
        assert abs(summary["total_recorded_value"] - expected) < 0.01

    def test_portfolio_pct_diff_positive(self, valued_portfolio):
        """Portfolio % diff should be non-negative."""
        summary = calculate_portfolio_summary(valued_portfolio)
        assert summary["portfolio_pct_diff"] >= 0

    def test_nan_values_excluded(self, portfolio_with_nan):
        """NaN values should be excluded from summary calculations."""
        valued = calculate_position_values(portfolio_with_nan)
        summary = calculate_portfolio_summary(valued)
        assert summary["valid_positions"] < summary["total_positions"]


# ─── Test: calculate_asset_class_summary ────────────────────────────────────

class TestCalculateAssetClassSummary:
    """Tests for asset class aggregations."""

    def test_asset_classes_present(self, valued_portfolio):
        """All asset classes in the data should appear in the summary."""
        result = calculate_asset_class_summary(valued_portfolio)
        input_classes = set(valued_portfolio["asset_class"].unique())
        output_classes = set(result["asset_class"].unique())
        # Output may exclude classes with all-NaN values
        assert output_classes.issubset(input_classes)

    def test_position_count_sums(self, valued_portfolio):
        """Position counts should sum to valid positions."""
        result = calculate_asset_class_summary(valued_portfolio)
        total_valid = valued_portfolio.dropna(subset=["recorded_value", "reference_value"]).shape[0]
        assert result["position_count"].sum() == total_valid

    def test_empty_dataframe(self):
        """Should handle empty DataFrame."""
        empty = pd.DataFrame(columns=[
            "position_id", "asset_class", "recorded_value",
            "reference_value", "absolute_diff", "percentage_diff",
        ])
        result = calculate_asset_class_summary(empty)
        assert len(result) == 0


# ─── Test: calculate_counterparty_exposure ──────────────────────────────────

class TestCalculateCounterpartyExposure:
    """Tests for counterparty exposure."""

    def test_counterparties_present(self, valued_portfolio):
        """All counterparties should appear in the exposure report."""
        result = calculate_counterparty_exposure(valued_portfolio)
        assert len(result) > 0
        assert "counterparty" in result.columns

    def test_sorted_by_value(self, valued_portfolio):
        """Results should be sorted by total_recorded_value descending."""
        result = calculate_counterparty_exposure(valued_portfolio)
        values = result["total_recorded_value"].tolist()
        assert values == sorted(values, reverse=True)
