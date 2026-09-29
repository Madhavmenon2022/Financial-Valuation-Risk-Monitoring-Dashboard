"""
Automated Reconciliation Engine
================================
Matches internal portfolio positions with independent market reference price feeds.
Detects:
  - Unmatched internal positions (missing market price)
  - Unmatched reference prices (market feed record without position)
  - Stale reference prices (market price date older than position date)
  - Duplicate positions/prices
  - Price valuation mismatches exceeding threshold limits
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple, Dict, Any, Union, Optional
from pathlib import Path
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import DEFAULT_THRESHOLD_PCT, WARNING_THRESHOLD_PCT, CRITICAL_THRESHOLD_PCT


def run_reconciliation(
    internal_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    stale_days_threshold: int = 1,
    warning_pct: float = WARNING_THRESHOLD_PCT,
    default_pct: float = DEFAULT_THRESHOLD_PCT,
    critical_pct: float = CRITICAL_THRESHOLD_PCT,
) -> Dict[str, Any]:
    """
    Perform automated reconciliation between internal position records and reference price feeds.

    Parameters
    ----------
    internal_df : pd.DataFrame
        Internal position data containing instrument_id, quantity, recorded_price, valuation_date.
    reference_df : pd.DataFrame
        Market reference price data containing instrument_id, reference_price, valuation_date.
    stale_days_threshold : int
        Max allowed difference in days before a market price is flagged as stale.
    warning_pct, default_pct, critical_pct : float
        Price mismatch variance thresholds.

    Returns
    -------
    dict
        - 'matched_df': Merged records with calculated valuation metrics
        - 'exceptions_df': Exception report containing all flagged discrepancies
        - 'unmatched_internal': Internal positions with no market reference match
        - 'unmatched_reference': Reference market prices with no internal position match
        - 'summary': High-level reconciliation summary statistics
    """
    # ── Normalize Column Headers ─────────────────────────────────────────────
    internal = _normalize_internal_df(internal_df)
    reference = _normalize_reference_df(reference_df)

    if len(internal) == 0 and len(reference) == 0:
        return _empty_reconciliation_result()

    # ── Convert Valuation Dates ──────────────────────────────────────────────
    internal["val_date_dt"] = pd.to_datetime(internal["valuation_date"], errors="coerce")
    reference["ref_date_dt"] = pd.to_datetime(reference["valuation_date"], errors="coerce")

    # ── Detect Duplicates in Source Datasets ─────────────────────────────────
    dup_internal = internal[internal.duplicated(subset=["instrument_id", "valuation_date"], keep=False)].copy()
    dup_reference = reference[reference.duplicated(subset=["instrument_id", "valuation_date"], keep=False)].copy()

    # De-duplicate for primary matching (keep first)
    internal_clean = internal.drop_duplicates(subset=["instrument_id", "valuation_date"], keep="first")
    reference_clean = reference.drop_duplicates(subset=["instrument_id", "valuation_date"], keep="first")

    # ── Record Matching (Full Outer Join on instrument_id) ────────────────────
    # First match exact instrument_id
    merged = pd.merge(
        internal_clean,
        reference_clean,
        on="instrument_id",
        how="outer",
        suffixes=("_int", "_ref")
    )

    # ── Categorize Match Results ────────────────────────────────────────────
    # 1. Matched records (both internal and reference exist)
    matched = merged[merged["recorded_price"].notna() & merged["reference_price"].notna()].copy()

    # 2. Unmatched internal (internal exists, reference is NaN)
    unmatched_int = merged[merged["recorded_price"].notna() & merged["reference_price"].isna()].copy()

    # 3. Unmatched reference (reference exists, internal is NaN)
    unmatched_ref = merged[merged["recorded_price"].isna() & merged["reference_price"].notna()].copy()

    # ── Process Matched Records & Compute Valuation Metrics ──────────────────
    if len(matched) > 0:
        matched["recorded_value"] = (matched["quantity"] * matched["recorded_price"]).round(2)
        matched["reference_value"] = (matched["quantity"] * matched["reference_price"]).round(2)
        matched["absolute_diff"] = (matched["recorded_value"] - matched["reference_value"]).abs().round(2)

        # Percentage diff calculation
        pct_diff = np.where(
            matched["reference_value"].abs() > 1e-10,
            (matched["absolute_diff"] / matched["reference_value"].abs()) * 100,
            np.where(matched["absolute_diff"].abs() > 1e-10, 100.0, 0.0)
        )
        matched["percentage_diff"] = pd.Series(pct_diff, index=matched.index, dtype=float).round(4)

        # Stale Price Check: date difference between internal valuation date and reference date
        matched["date_diff_days"] = (matched["val_date_dt"] - matched["ref_date_dt"]).dt.days
        matched["is_stale"] = matched["date_diff_days"] > stale_days_threshold
    else:
        matched["recorded_value"] = []
        matched["reference_value"] = []
        matched["absolute_diff"] = []
        matched["percentage_diff"] = []
        matched["date_diff_days"] = []
        matched["is_stale"] = []

    # ── Build Reconciliation Exceptions ─────────────────────────────────────
    exceptions_list = []

    # A) Unmatched Internal Positions
    for _, row in unmatched_int.iterrows():
        exceptions_list.append({
            "exception_id": f"EXC-REC-UI-{row.get('position_id', 'POS')}",
            "position_id": row.get("position_id", "N/A"),
            "instrument_id": row["instrument_id"],
            "asset_class": row.get("asset_class", "Unknown"),
            "counterparty": row.get("counterparty", "N/A"),
            "currency": row.get("currency", "USD"),
            "quantity": row.get("quantity", 0),
            "recorded_price": row.get("recorded_price", np.nan),
            "reference_price": np.nan,
            "percentage_diff": np.nan,
            "exception_type": "Unmatched Internal",
            "severity": "Critical",
            "reason": f"Internal position {row['instrument_id']} has no matching reference market price.",
            "status": "Open",
            "analyst_notes": "",
        })

    # B) Unmatched Reference Market Feed Records
    for _, row in unmatched_ref.iterrows():
        exceptions_list.append({
            "exception_id": f"EXC-REC-UR-{row['instrument_id']}",
            "position_id": "N/A",
            "instrument_id": row["instrument_id"],
            "asset_class": "Market Feed",
            "counterparty": "Market Feed",
            "currency": row.get("currency", "USD"),
            "quantity": 0,
            "recorded_price": np.nan,
            "reference_price": row.get("reference_price", np.nan),
            "percentage_diff": np.nan,
            "exception_type": "Unmatched Reference",
            "severity": "Warning",
            "reason": f"Reference price feed contains {row['instrument_id']} but no internal position exists.",
            "status": "Open",
            "analyst_notes": "",
        })

    # C) Stale Reference Prices
    stale_rows = matched[matched["is_stale"]].copy()
    for _, row in stale_rows.iterrows():
        days = int(row["date_diff_days"])
        exceptions_list.append({
            "exception_id": f"EXC-REC-SP-{row.get('position_id', row['instrument_id'])}",
            "position_id": row.get("position_id", "N/A"),
            "instrument_id": row["instrument_id"],
            "asset_class": row.get("asset_class", "Unknown"),
            "counterparty": row.get("counterparty", "N/A"),
            "currency": row.get("currency", "USD"),
            "quantity": row.get("quantity", 0),
            "recorded_price": row.get("recorded_price", np.nan),
            "reference_price": row.get("reference_price", np.nan),
            "percentage_diff": row.get("percentage_diff", 0.0),
            "exception_type": "Stale Price",
            "severity": "High" if days > 3 else "Warning",
            "reason": f"Market price date ({row.get('valuation_date_ref', 'N/A')}) is {days} days older than position date ({row.get('valuation_date_int', 'N/A')}).",
            "status": "Open",
            "analyst_notes": "",
        })

    # D) Price Mismatches / Threshold Breaches
    breach_rows = matched[matched["percentage_diff"] > warning_pct].copy()
    for _, row in breach_rows.iterrows():
        pct = float(row["percentage_diff"])
        sev = "Critical" if pct >= critical_pct else ("High" if pct >= default_pct else "Warning")
        exceptions_list.append({
            "exception_id": f"EXC-REC-TB-{row.get('position_id', row['instrument_id'])}",
            "position_id": row.get("position_id", "N/A"),
            "instrument_id": row["instrument_id"],
            "asset_class": row.get("asset_class", "Unknown"),
            "counterparty": row.get("counterparty", "N/A"),
            "currency": row.get("currency", "USD"),
            "quantity": row.get("quantity", 0),
            "recorded_price": row.get("recorded_price", np.nan),
            "reference_price": row.get("reference_price", np.nan),
            "percentage_diff": pct,
            "exception_type": "Threshold Breach",
            "severity": sev,
            "reason": f"Valuation discrepancy of {pct:.2f}% exceeds warning threshold ({warning_pct}%).",
            "status": "Open",
            "analyst_notes": "",
        })

    # E) Duplicates in Internal Datasets
    for _, row in dup_internal.iterrows():
        exceptions_list.append({
            "exception_id": f"EXC-REC-DP-{row.get('position_id', row['instrument_id'])}",
            "position_id": row.get("position_id", "N/A"),
            "instrument_id": row["instrument_id"],
            "asset_class": row.get("asset_class", "Unknown"),
            "counterparty": row.get("counterparty", "N/A"),
            "currency": row.get("currency", "USD"),
            "quantity": row.get("quantity", 0),
            "recorded_price": row.get("recorded_price", np.nan),
            "reference_price": np.nan,
            "percentage_diff": np.nan,
            "exception_type": "Duplicate Position",
            "severity": "High",
            "reason": f"Duplicate booking of instrument {row['instrument_id']} on valuation date {row.get('valuation_date', 'N/A')}.",
            "status": "Open",
            "analyst_notes": "",
        })

    exceptions_df = pd.DataFrame(exceptions_list)

    if len(exceptions_df) > 0:
        # De-duplicate exception list by exception_id
        exceptions_df = exceptions_df.drop_duplicates(subset=["exception_id"]).reset_index(drop=True)
        # Sync with SQLite database
        try:
            from src.database import sync_exceptions
            exceptions_df = sync_exceptions(exceptions_df)
        except Exception:
            pass

    # ── Summary Metrics ──────────────────────────────────────────────────────
    total_int = len(internal)
    total_ref = len(reference)
    total_matched = len(matched)
    total_unmatched_int = len(unmatched_int)
    total_unmatched_ref = len(unmatched_ref)
    stale_count = len(stale_rows)
    mismatch_count = len(breach_rows)
    total_var = float(matched["absolute_diff"].sum()) if len(matched) > 0 else 0.0

    match_rate = round((total_matched / total_int * 100), 1) if total_int > 0 else 0.0

    summary = {
        "total_internal_positions": total_int,
        "total_reference_records": total_ref,
        "matched_count": total_matched,
        "match_rate_pct": match_rate,
        "unmatched_internal_count": total_unmatched_int,
        "unmatched_reference_count": total_unmatched_ref,
        "stale_price_count": stale_count,
        "mismatch_count": mismatch_count,
        "total_exceptions_count": len(exceptions_df),
        "total_variance_usd": round(total_var, 2),
    }

    return {
        "matched_df": matched,
        "exceptions_df": exceptions_df if len(exceptions_df) > 0 else _empty_exception_df(),
        "unmatched_internal": unmatched_int,
        "unmatched_reference": unmatched_ref,
        "summary": summary,
    }


def _normalize_internal_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize internal position DataFrame column names (case-insensitive)."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=[
            "position_id", "instrument_id", "asset_class", "counterparty",
            "currency", "quantity", "recorded_price", "valuation_date"
        ])
    df_clean = df.copy()
    col_map = {
        "pos_id": "position_id",
        "position id": "position_id",
        "instrument": "instrument_id",
        "instrument id": "instrument_id",
        "asset": "asset_class",
        "asset class": "asset_class",
        "qty": "quantity",
        "quantity": "quantity",
        "price": "recorded_price",
        "recorded price": "recorded_price",
        "book_price": "recorded_price",
        "date": "valuation_date",
        "valuation date": "valuation_date",
    }
    df_clean.columns = [col_map.get(str(c).strip().lower(), c) for c in df_clean.columns]
    if "position_id" not in df_clean.columns:
        df_clean["position_id"] = [f"POS-{i+1:05d}" for i in range(len(df_clean))]
    return df_clean


def _normalize_reference_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize reference price DataFrame column names (case-insensitive)."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["instrument_id", "reference_price", "valuation_date"])
    df_clean = df.copy()
    col_map = {
        "instrument": "instrument_id",
        "instrument id": "instrument_id",
        "market_price": "reference_price",
        "price": "reference_price",
        "reference price": "reference_price",
        "ref_price": "reference_price",
        "as_of_date": "valuation_date",
        "as of date": "valuation_date",
        "price date": "valuation_date",
        "valuation date": "valuation_date",
    }
    df_clean.columns = [col_map.get(str(c).strip().lower(), c) for c in df_clean.columns]
    return df_clean


def _empty_reconciliation_result() -> Dict[str, Any]:
    """Return an empty reconciliation result dictionary."""
    return {
        "matched_df": pd.DataFrame(),
        "exceptions_df": _empty_exception_df(),
        "unmatched_internal": pd.DataFrame(),
        "unmatched_reference": pd.DataFrame(),
        "summary": {
            "total_internal_positions": 0,
            "total_reference_records": 0,
            "matched_count": 0,
            "match_rate_pct": 0.0,
            "unmatched_internal_count": 0,
            "unmatched_reference_count": 0,
            "stale_price_count": 0,
            "mismatch_count": 0,
            "total_exceptions_count": 0,
            "total_variance_usd": 0.0,
        }
    }


def _empty_exception_df() -> pd.DataFrame:
    """Return empty exceptions DataFrame with standard schema."""
    return pd.DataFrame(columns=[
        "exception_id", "position_id", "instrument_id", "asset_class",
        "counterparty", "currency", "quantity", "recorded_price", "reference_price",
        "percentage_diff", "exception_type", "severity", "reason", "status", "analyst_notes"
    ])
