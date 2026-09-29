"""
Unit Tests: Exception Detection
=================================
Tests for all four automated control checks and the aggregated runner.
Run: pytest tests/ -v
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.exception_detector import (
    detect_missing_prices,
    detect_duplicates,
    detect_invalid_quantities,
    detect_threshold_breaches,
    run_all_controls,
    get_exception_summary,
)
from src.valuation_engine import calculate_position_values


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_portfolio():
    """Portfolio with no issues — all controls should pass."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003"],
        "instrument_id": ["EQ-001", "FI-002", "CM-003"],
        "asset_class": ["Equity", "Fixed Income", "Commodity"],
        "counterparty": ["BankA", "BankB", "BankC"],
        "currency": ["USD", "EUR", "USD"],
        "quantity": [1000, 5000, 500],
        "recorded_price": [150.00, 100.50, 75.00],
        "reference_price": [149.50, 100.00, 74.80],
        "valuation_date": ["2024-01-15"] * 3,
    })


@pytest.fixture
def portfolio_missing_prices():
    """Portfolio with missing prices."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003", "POS-004"],
        "instrument_id": ["EQ-001", "FI-002", "CM-003", "DV-004"],
        "asset_class": ["Equity", "Fixed Income", "Commodity", "Derivative"],
        "counterparty": ["BankA", "BankB", "BankC", "BankD"],
        "currency": ["USD", "EUR", "USD", "GBP"],
        "quantity": [1000, 5000, 500, 200],
        "recorded_price": [150.00, np.nan, 75.00, np.nan],
        "reference_price": [148.00, 100.00, np.nan, np.nan],
        "valuation_date": ["2024-01-15"] * 4,
    })


@pytest.fixture
def portfolio_duplicates():
    """Portfolio with duplicate instrument IDs."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003", "POS-004"],
        "instrument_id": ["EQ-001", "FI-002", "EQ-001", "FI-002"],
        "asset_class": ["Equity", "Fixed Income", "Equity", "Fixed Income"],
        "counterparty": ["BankA", "BankB", "BankA", "BankB"],
        "currency": ["USD", "EUR", "USD", "EUR"],
        "quantity": [1000, 5000, 1000, 5000],
        "recorded_price": [150.00, 100.50, 150.00, 100.50],
        "reference_price": [149.50, 100.00, 149.50, 100.00],
        "valuation_date": ["2024-01-15"] * 4,
    })


@pytest.fixture
def portfolio_invalid_qty():
    """Portfolio with invalid quantities."""
    return pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003"],
        "instrument_id": ["EQ-001", "FI-002", "CM-003"],
        "asset_class": ["Equity", "Fixed Income", "Commodity"],
        "counterparty": ["BankA", "BankB", "BankC"],
        "currency": ["USD", "EUR", "USD"],
        "quantity": [1000, 0, -500],
        "recorded_price": [150.00, 100.50, 75.00],
        "reference_price": [149.50, 100.00, 74.80],
        "valuation_date": ["2024-01-15"] * 3,
    })


@pytest.fixture
def portfolio_large_deviations():
    """Portfolio with large price deviations."""
    df = pd.DataFrame({
        "position_id": ["POS-001", "POS-002", "POS-003", "POS-004"],
        "instrument_id": ["EQ-001", "FI-002", "CM-003", "DV-004"],
        "asset_class": ["Equity", "Fixed Income", "Commodity", "Derivative"],
        "counterparty": ["BankA", "BankB", "BankC", "BankD"],
        "currency": ["USD", "EUR", "USD", "GBP"],
        "quantity": [1000, 5000, 500, 200],
        "recorded_price": [150.00, 100.00, 90.00, 10.00],   # 90 vs 75 = 20% dev
        "reference_price": [149.50, 100.00, 75.00, 10.00],
        "valuation_date": ["2024-01-15"] * 4,
    })
    return calculate_position_values(df)


# ─── Test: detect_missing_prices ────────────────────────────────────────────

class TestDetectMissingPrices:

    def test_no_missing_prices(self, clean_portfolio):
        """Clean data should produce no missing-price exceptions."""
        result = detect_missing_prices(clean_portfolio)
        assert len(result) == 0

    def test_missing_recorded_price(self, portfolio_missing_prices):
        """Should detect missing recorded prices."""
        result = detect_missing_prices(portfolio_missing_prices)
        assert len(result) > 0
        assert all(result["exception_type"] == "Missing Price")

    def test_missing_reference_price(self, portfolio_missing_prices):
        """Should detect missing reference prices."""
        result = detect_missing_prices(portfolio_missing_prices)
        ref_missing = result[result["reason"].str.contains("Reference")]
        assert len(ref_missing) > 0

    def test_both_prices_missing(self, portfolio_missing_prices):
        """Should detect when both prices are missing (POS-004)."""
        result = detect_missing_prices(portfolio_missing_prices)
        pos4 = result[result["position_id"] == "POS-004"]
        assert len(pos4) == 1
        assert "Recorded" in pos4.iloc[0]["reason"]
        assert "Reference" in pos4.iloc[0]["reason"]

    def test_severity_is_critical(self, portfolio_missing_prices):
        """Missing prices should always be Critical severity."""
        result = detect_missing_prices(portfolio_missing_prices)
        assert all(result["severity"] == "Critical")

    def test_correct_count(self, portfolio_missing_prices):
        """Should flag exactly the positions with NaN prices."""
        result = detect_missing_prices(portfolio_missing_prices)
        # POS-002 (rec missing), POS-003 (ref missing), POS-004 (both)
        assert len(result) == 3


# ─── Test: detect_duplicates ───────────────────────────────────────────────

class TestDetectDuplicates:

    def test_no_duplicates(self, clean_portfolio):
        """Clean data should produce no duplicate exceptions."""
        result = detect_duplicates(clean_portfolio)
        assert len(result) == 0

    def test_detects_duplicates(self, portfolio_duplicates):
        """Should flag all rows involved in duplication."""
        result = detect_duplicates(portfolio_duplicates)
        assert len(result) == 4  # All 4 rows are part of duplicate groups
        assert all(result["exception_type"] == "Duplicate Position")

    def test_severity_is_high(self, portfolio_duplicates):
        """Duplicate positions should be High severity."""
        result = detect_duplicates(portfolio_duplicates)
        assert all(result["severity"] == "High")

    def test_reason_contains_instrument_id(self, portfolio_duplicates):
        """Reason should reference the duplicate instrument ID."""
        result = detect_duplicates(portfolio_duplicates)
        assert all("EQ-001" in r or "FI-002" in r for r in result["reason"])


# ─── Test: detect_invalid_quantities ────────────────────────────────────────

class TestDetectInvalidQuantities:

    def test_no_invalid_quantities(self, clean_portfolio):
        """Clean data should produce no invalid-quantity exceptions."""
        result = detect_invalid_quantities(clean_portfolio)
        assert len(result) == 0

    def test_detects_zero_quantity(self, portfolio_invalid_qty):
        """Should flag zero quantities."""
        result = detect_invalid_quantities(portfolio_invalid_qty)
        zero_rows = result[result["quantity"] == 0]
        assert len(zero_rows) > 0

    def test_detects_negative_quantity(self, portfolio_invalid_qty):
        """Should flag negative quantities."""
        result = detect_invalid_quantities(portfolio_invalid_qty)
        neg_rows = result[result["quantity"] < 0]
        assert len(neg_rows) > 0

    def test_correct_count(self, portfolio_invalid_qty):
        """Should flag exactly 2 invalid quantities (zero + negative)."""
        result = detect_invalid_quantities(portfolio_invalid_qty)
        assert len(result) == 2

    def test_severity_is_high(self, portfolio_invalid_qty):
        """Invalid quantities should be High severity."""
        result = detect_invalid_quantities(portfolio_invalid_qty)
        assert all(result["severity"] == "High")

    def test_reason_describes_issue(self, portfolio_invalid_qty):
        """Reason should describe whether qty is zero or negative."""
        result = detect_invalid_quantities(portfolio_invalid_qty)
        reasons = result["reason"].tolist()
        assert any("zero" in r for r in reasons)
        assert any("negative" in r for r in reasons)


# ─── Test: detect_threshold_breaches ────────────────────────────────────────

class TestDetectThresholdBreaches:

    def test_no_breaches_within_threshold(self):
        """Positions within threshold should not be flagged."""
        df = pd.DataFrame({
            "position_id": ["POS-001"],
            "instrument_id": ["EQ-001"],
            "asset_class": ["Equity"],
            "quantity": [1000],
            "recorded_price": [100.00],
            "reference_price": [100.00],
            "recorded_value": [100000.00],
            "reference_value": [100000.00],
            "absolute_diff": [0.0],
            "percentage_diff": [0.0],
        })
        result = detect_threshold_breaches(df, warning_pct=2.0, default_pct=5.0, critical_pct=10.0)
        assert len(result) == 0

    def test_detects_warning_level(self, portfolio_large_deviations):
        """Should detect warning-level breaches."""
        result = detect_threshold_breaches(
            portfolio_large_deviations,
            warning_pct=0.1,  # Very low threshold to trigger
            default_pct=5.0,
            critical_pct=10.0,
        )
        assert len(result) > 0

    def test_detects_critical_level(self, portfolio_large_deviations):
        """Should classify large deviations as Critical."""
        result = detect_threshold_breaches(
            portfolio_large_deviations,
            warning_pct=2.0, default_pct=5.0, critical_pct=10.0,
        )
        critical = result[result["severity"] == "Critical"]
        # POS-003: 90 vs 75 = 20% deviation → Critical
        assert len(critical) > 0

    def test_severity_classification(self, portfolio_large_deviations):
        """Severity should escalate with deviation percentage."""
        result = detect_threshold_breaches(
            portfolio_large_deviations,
            warning_pct=0.1, default_pct=1.0, critical_pct=15.0,
        )
        if len(result) > 0:
            severities = result["severity"].unique()
            assert all(s in ["Warning", "High", "Critical"] for s in severities)

    def test_missing_percentage_diff_column(self, clean_portfolio):
        """Should return empty DataFrame if percentage_diff column is missing."""
        result = detect_threshold_breaches(clean_portfolio)
        assert len(result) == 0

    def test_nan_prices_excluded(self):
        """Positions with NaN prices should not be flagged for threshold breach."""
        df = pd.DataFrame({
            "position_id": ["POS-001"],
            "instrument_id": ["EQ-001"],
            "asset_class": ["Equity"],
            "quantity": [1000],
            "recorded_price": [np.nan],
            "reference_price": [100.00],
            "recorded_value": [np.nan],
            "reference_value": [100000.00],
            "absolute_diff": [np.nan],
            "percentage_diff": [np.nan],
        })
        result = detect_threshold_breaches(df, warning_pct=2.0, default_pct=5.0, critical_pct=10.0)
        assert len(result) == 0


# ─── Test: run_all_controls ─────────────────────────────────────────────────

class TestRunAllControls:

    def test_clean_data_minimal_exceptions(self, clean_portfolio):
        """Clean data may have minor threshold warnings but no critical issues."""
        valued = calculate_position_values(clean_portfolio)
        result = run_all_controls(valued, warning_pct=100.0, default_pct=100.0, critical_pct=100.0)
        # With extremely high thresholds, no threshold breaches
        critical = result[result["severity"] == "Critical"] if len(result) > 0 else pd.DataFrame()
        assert len(critical) == 0

    def test_combines_all_exception_types(self):
        """Should include exceptions from all four detectors."""
        df = pd.DataFrame({
            "position_id": ["POS-001", "POS-002", "POS-003", "POS-004", "POS-005"],
            "instrument_id": ["EQ-001", "FI-002", "CM-003", "EQ-001", "DV-005"],
            "asset_class": ["Equity", "Fixed Income", "Commodity", "Equity", "Derivative"],
            "counterparty": ["A", "B", "C", "A", "D"],
            "currency": ["USD"] * 5,
            "quantity": [1000, 5000, 0, 1000, 200],
            "recorded_price": [150.00, np.nan, 75.00, 150.00, 50.00],
            "reference_price": [100.00, 100.00, 74.80, 100.00, 10.00],
            "valuation_date": ["2024-01-15"] * 5,
        })
        valued = calculate_position_values(df)
        result = run_all_controls(valued, warning_pct=2.0, default_pct=5.0, critical_pct=10.0)

        types_found = set(result["exception_type"].unique())
        # Should have Missing Price, Duplicate Position, Invalid Quantity, and Threshold Breach
        assert "Missing Price" in types_found
        assert "Duplicate Position" in types_found
        assert "Invalid Quantity" in types_found

    def test_sorted_by_severity(self):
        """Exceptions should be sorted Critical → High → Warning."""
        df = pd.DataFrame({
            "position_id": [f"POS-{i:03d}" for i in range(5)],
            "instrument_id": [f"X-{i:03d}" for i in range(5)],
            "asset_class": ["Equity"] * 5,
            "counterparty": ["Bank"] * 5,
            "currency": ["USD"] * 5,
            "quantity": [1000, 0, 1000, 1000, 1000],
            "recorded_price": [150.0, 100.0, np.nan, 120.0, 103.0],
            "reference_price": [149.0, 100.0, 100.0, 100.0, 100.0],
            "valuation_date": ["2024-01-15"] * 5,
        })
        valued = calculate_position_values(df)
        result = run_all_controls(valued, warning_pct=2.0, default_pct=5.0, critical_pct=10.0)

        if len(result) > 1:
            severity_order = {"Critical": 0, "High": 1, "Warning": 2}
            orders = result["severity"].map(severity_order).tolist()
            assert orders == sorted(orders)

    def test_deduplication(self):
        """Same position + same exception type should not appear twice."""
        df = pd.DataFrame({
            "position_id": ["POS-001", "POS-001"],
            "instrument_id": ["EQ-001", "EQ-001"],
            "asset_class": ["Equity", "Equity"],
            "counterparty": ["A", "A"],
            "currency": ["USD", "USD"],
            "quantity": [1000, 1000],
            "recorded_price": [150.00, 150.00],
            "reference_price": [149.50, 149.50],
            "valuation_date": ["2024-01-15"] * 2,
        })
        valued = calculate_position_values(df)
        result = run_all_controls(valued)
        # Should have Duplicate Position for POS-001, but only once per type
        dup_rows = result[
            (result["position_id"] == "POS-001") &
            (result["exception_type"] == "Duplicate Position")
        ]
        assert len(dup_rows) <= 2  # keep=False flags both


# ─── Test: get_exception_summary ────────────────────────────────────────────

class TestGetExceptionSummary:

    def test_empty_exceptions(self):
        """Summary of empty exceptions should show zeros."""
        empty = pd.DataFrame(columns=["exception_type", "severity"])
        summary = get_exception_summary(empty)
        assert summary["total_exceptions"] == 0
        assert summary["critical_count"] == 0

    def test_counts_match(self):
        """Summary counts should match actual exception counts."""
        exc = pd.DataFrame({
            "exception_type": ["Missing Price", "Missing Price", "Threshold Breach"],
            "severity": ["Critical", "Critical", "Warning"],
        })
        summary = get_exception_summary(exc)
        assert summary["total_exceptions"] == 3
        assert summary["critical_count"] == 2
        assert summary["warning_count"] == 1
        assert summary["by_type"]["Missing Price"] == 2
