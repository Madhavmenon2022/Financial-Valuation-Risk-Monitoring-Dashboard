"""
Unit tests for the Automated Reconciliation Engine (src/reconciliation_engine.py).
Tests record matching, stale price detection, unmatched position/reference handling, and edge cases.
"""

import pytest
import pandas as pd
import numpy as np
from src.reconciliation_engine import run_reconciliation


@pytest.fixture
def sample_internal_df():
    return pd.DataFrame([
        {
            "position_id": "POS-001",
            "instrument_id": "EQ-AAPL-001",
            "asset_class": "Equity",
            "counterparty": "GlobalBank",
            "currency": "USD",
            "quantity": 1000,
            "recorded_price": 150.0,
            "valuation_date": "2026-09-29",
        },
        {
            "position_id": "POS-002",
            "instrument_id": "FI-US10Y-002",
            "asset_class": "Fixed Income",
            "counterparty": "Apex Trading",
            "currency": "USD",
            "quantity": 5000,
            "recorded_price": 98.50,
            "valuation_date": "2026-09-29",
        },
        {
            "position_id": "POS-003",
            "instrument_id": "FX-EURUSD-003",
            "asset_class": "FX Forward",
            "counterparty": "Sterling",
            "currency": "EUR/USD",
            "quantity": 100000,
            "recorded_price": 1.0850,
            "valuation_date": "2026-09-29",
        },
    ])


@pytest.fixture
def sample_reference_df():
    return pd.DataFrame([
        {
            "instrument_id": "EQ-AAPL-001",
            "reference_price": 150.25,
            "valuation_date": "2026-09-29",
            "source": "Bloomberg",
        },
        {
            "instrument_id": "FI-US10Y-002",
            "reference_price": 110.00,  # Large deviation
            "valuation_date": "2026-09-29",
            "source": "Reuters",
        },
        {
            "instrument_id": "FX-EURUSD-003",
            "reference_price": 1.0850,
            "valuation_date": "2026-09-24",  # Stale date (5 days ago)
            "source": "Markit",
        },
        {
            "instrument_id": "CM-GOLD-999",  # Unmatched reference record
            "reference_price": 2000.0,
            "valuation_date": "2026-09-29",
            "source": "ICE",
        },
    ])


class TestReconciliationEngine:
    def test_record_matching(self, sample_internal_df, sample_reference_df):
        res = run_reconciliation(sample_internal_df, sample_reference_df)
        summary = res["summary"]

        assert summary["total_internal_positions"] == 3
        assert summary["total_reference_records"] == 4
        assert summary["matched_count"] == 3
        assert summary["unmatched_reference_count"] == 1

    def test_stale_price_detection(self, sample_internal_df, sample_reference_df):
        res = run_reconciliation(sample_internal_df, sample_reference_df, stale_days_threshold=1)
        exceptions = res["exceptions_df"]
        stale_exc = exceptions[exceptions["exception_type"] == "Stale Price"]

        assert len(stale_exc) == 1
        assert stale_exc.iloc[0]["instrument_id"] == "FX-EURUSD-003"

    def test_price_mismatch_detection(self, sample_internal_df, sample_reference_df):
        res = run_reconciliation(sample_internal_df, sample_reference_df, default_pct=5.0)
        exceptions = res["exceptions_df"]
        mismatch_exc = exceptions[exceptions["exception_type"] == "Threshold Breach"]

        assert len(mismatch_exc) >= 1
        assert "FI-US10Y-002" in mismatch_exc["instrument_id"].values

    def test_unmatched_internal_positions(self, sample_internal_df, sample_reference_df):
        # Remove FX-EURUSD-003 from reference feed
        ref_subset = sample_reference_df[sample_reference_df["instrument_id"] != "FX-EURUSD-003"]
        res = run_reconciliation(sample_internal_df, ref_subset)
        summary = res["summary"]
        exceptions = res["exceptions_df"]

        assert summary["unmatched_internal_count"] == 1
        unmatched_exc = exceptions[exceptions["exception_type"] == "Unmatched Internal"]
        assert len(unmatched_exc) == 1
        assert unmatched_exc.iloc[0]["instrument_id"] == "FX-EURUSD-003"

    def test_empty_inputs(self):
        empty_df = pd.DataFrame()
        res = run_reconciliation(empty_df, empty_df)
        assert res["summary"]["total_internal_positions"] == 0
        assert res["summary"]["matched_count"] == 0
        assert len(res["exceptions_df"]) == 0

    def test_column_alias_normalization(self):
        internal_aliased = pd.DataFrame([{
            "Position ID": "POS-X",
            "Instrument ID": "EQ-TEST",
            "Recorded Price": 100.0,
            "Quantity": 10,
            "Valuation Date": "2026-09-29"
        }])
        ref_aliased = pd.DataFrame([{
            "Instrument ID": "EQ-TEST",
            "Price": 102.0,
            "As Of Date": "2026-09-29"
        }])
        res = run_reconciliation(internal_aliased, ref_aliased)
        assert res["summary"]["matched_count"] == 1
