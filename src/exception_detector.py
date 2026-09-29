"""
Exception Detector (Automated Controls)
=========================================
Implements the daily valuation control checks:
  1. Missing Prices      – positions with NaN recorded or reference prices
  2. Duplicate Positions – rows sharing the same instrument_id
  3. Invalid Quantities  – zero or negative quantities
  4. Threshold Breaches  – percentage differences exceeding configurable limits

Each detector returns a DataFrame of flagged exceptions with severity and
descriptive reason codes.
"""

import pandas as pd
import numpy as np
from typing import List
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    DEFAULT_THRESHOLD_PCT,
    WARNING_THRESHOLD_PCT,
    CRITICAL_THRESHOLD_PCT,
)


# ─── Individual Exception Detectors ────────────────────────────────────────────

def detect_missing_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag positions where recorded_price or reference_price is missing (NaN).

    Returns
    -------
    pd.DataFrame
        Rows with exception_type = 'Missing Price' and details on which price is missing.
    """
    mask_rec = df["recorded_price"].isna()
    mask_ref = df["reference_price"].isna()
    mask = mask_rec | mask_ref

    exceptions = df[mask].copy()

    if len(exceptions) == 0:
        return _empty_exception_df(df)

    exceptions["exception_type"] = "Missing Price"
    exceptions["severity"] = "Critical"
    exceptions["reason"] = exceptions.apply(
        lambda r: _missing_reason(r["recorded_price"], r["reference_price"]),
        axis=1,
    )
    return exceptions


def _missing_reason(recorded, reference) -> str:
    parts = []
    if pd.isna(recorded):
        parts.append("Recorded price is missing")
    if pd.isna(reference):
        parts.append("Reference price is missing")
    return "; ".join(parts)


def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag duplicate positions sharing the same instrument_id.

    Returns
    -------
    pd.DataFrame
        Duplicate rows with exception_type = 'Duplicate Position'.
    """
    dup_mask = df.duplicated(subset=["instrument_id"], keep=False)
    dupes = df[dup_mask].copy()

    if len(dupes) == 0:
        return _empty_exception_df(df)

    dupes["exception_type"] = "Duplicate Position"
    dupes["severity"] = "High"
    dupes["reason"] = dupes["instrument_id"].apply(
        lambda x: f"Duplicate instrument_id: {x}"
    )
    return dupes


def detect_invalid_quantities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag positions with zero or negative quantities.

    Returns
    -------
    pd.DataFrame
        Rows with exception_type = 'Invalid Quantity'.
    """
    mask = df["quantity"] <= 0
    invalid = df[mask].copy()

    if len(invalid) == 0:
        return _empty_exception_df(df)

    invalid["exception_type"] = "Invalid Quantity"
    invalid["severity"] = "High"
    invalid["reason"] = invalid["quantity"].apply(
        lambda q: f"Quantity is {'zero' if q == 0 else 'negative'} ({q})"
    )
    return invalid


def detect_threshold_breaches(
    df: pd.DataFrame,
    warning_pct: float = WARNING_THRESHOLD_PCT,
    default_pct: float = DEFAULT_THRESHOLD_PCT,
    critical_pct: float = CRITICAL_THRESHOLD_PCT,
) -> pd.DataFrame:
    """
    Flag positions where the percentage valuation difference exceeds thresholds.

    Severity levels:
    - Warning:  percentage_diff > warning_pct
    - High:     percentage_diff > default_pct
    - Critical: percentage_diff > critical_pct

    Returns
    -------
    pd.DataFrame
        Rows with exception_type = 'Threshold Breach' and assigned severity.
    """
    if "percentage_diff" not in df.columns:
        return _empty_exception_df(df)

    mask = df["percentage_diff"] > warning_pct
    valid_mask = df["recorded_price"].notna() & df["reference_price"].notna()
    breaches = df[mask & valid_mask].copy()

    if len(breaches) == 0:
        return _empty_exception_df(df)

    breaches["exception_type"] = "Threshold Breach"

    breaches["severity"] = breaches["percentage_diff"].apply(
        lambda p: _classify_severity(p, warning_pct, default_pct, critical_pct)
    )

    breaches["reason"] = breaches["percentage_diff"].apply(
        lambda p: f"Valuation difference of {p:.2f}% exceeds threshold"
    )

    return breaches


def _classify_severity(
    pct: float, warning: float, default: float, critical: float
) -> str:
    if pct >= critical:
        return "Critical"
    elif pct >= default:
        return "High"
    else:
        return "Warning"


# ─── Aggregated Exception Runner ───────────────────────────────────────────────

def run_all_controls(
    df: pd.DataFrame,
    warning_pct: float = WARNING_THRESHOLD_PCT,
    default_pct: float = DEFAULT_THRESHOLD_PCT,
    critical_pct: float = CRITICAL_THRESHOLD_PCT,
) -> pd.DataFrame:
    """
    Execute all automated controls and return a unified exception report.

    Parameters
    ----------
    df : pd.DataFrame
        Valued portfolio (should already have percentage_diff column).
    warning_pct, default_pct, critical_pct : float
        Configurable threshold levels.

    Returns
    -------
    pd.DataFrame
        Combined exceptions from all detectors, sorted by severity.
    """
    detectors: List[pd.DataFrame] = [
        detect_missing_prices(df),
        detect_duplicates(df),
        detect_invalid_quantities(df),
        detect_threshold_breaches(df, warning_pct, default_pct, critical_pct),
    ]

    non_empty = [d for d in detectors if len(d) > 0]
    if not non_empty:
        return _empty_exception_df(df)

    all_exceptions = pd.concat(non_empty, ignore_index=True)

    # De-duplicate: if a position has multiple exception types, keep all unique
    all_exceptions = all_exceptions.drop_duplicates(
        subset=["position_id", "exception_type"]
    )

    # Sort: Critical first, then High, then Warning
    severity_order = {"Critical": 0, "High": 1, "Warning": 2}
    all_exceptions["_sev_order"] = all_exceptions["severity"].map(severity_order)
    all_exceptions = all_exceptions.sort_values(
        ["_sev_order", "percentage_diff"],
        ascending=[True, False],
        na_position="last",
    ).drop(columns=["_sev_order"])

    # Generate unique exception_id for each exception
    all_exceptions = _assign_exception_ids(all_exceptions)

    # Sync with SQLite database to preserve status/notes and record audit trail
    try:
        from src.database import sync_exceptions
        all_exceptions = sync_exceptions(all_exceptions)
    except Exception as e:
        # Fallback if DB sync fails
        if "status" not in all_exceptions.columns:
            all_exceptions["status"] = "Open"
            all_exceptions["analyst_notes"] = ""

    return all_exceptions.reset_index(drop=True)


def _assign_exception_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Generate deterministic, human-readable unique exception IDs."""
    if len(df) == 0:
        if "exception_id" not in df.columns:
            df["exception_id"] = ""
        return df

    type_codes = {
        "Missing Price": "MP",
        "Duplicate Position": "DP",
        "Invalid Quantity": "IQ",
        "Threshold Breach": "TB",
        "Stale Price": "SP",
        "Unmatched Reference": "UR",
        "Unmatched Internal": "UI",
    }

    ids = []
    for idx, row in df.iterrows():
        pos = str(row.get("position_id", f"POS-{idx+1:05d}"))
        exc_type = str(row.get("exception_type", "GEN"))
        code = type_codes.get(exc_type, "EXC")

        # Create unique, deterministic exception_id
        exc_id = f"EXC-{pos}-{code}"
        ids.append(exc_id)

    df["exception_id"] = ids
    # Move exception_id to first column
    cols = ["exception_id"] + [c for c in df.columns if c != "exception_id"]
    return df[cols]


def get_exception_summary(exceptions: pd.DataFrame) -> dict:
    """
    Summarize exceptions by type, severity, and workflow status.

    Returns
    -------
    dict
        Counts and breakdowns for dashboard display.
    """
    total = len(exceptions)

    by_type = exceptions["exception_type"].value_counts().to_dict() if total > 0 else {}
    by_severity = exceptions["severity"].value_counts().to_dict() if total > 0 else {}
    by_status = exceptions["status"].value_counts().to_dict() if "status" in exceptions.columns and total > 0 else {}

    return {
        "total_exceptions": total,
        "by_type": by_type,
        "by_severity": by_severity,
        "by_status": by_status,
        "critical_count": by_severity.get("Critical", 0),
        "high_count": by_severity.get("High", 0),
        "warning_count": by_severity.get("Warning", 0),
        "open_count": by_status.get("Open", total),
        "under_review_count": by_status.get("Under Review", 0),
        "resolved_count": by_status.get("Resolved", 0),
    }


def _empty_exception_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return an empty DataFrame with exception columns appended."""
    cols = ["exception_id"] + list(df.columns) + ["exception_type", "severity", "reason", "status", "analyst_notes"]
    return pd.DataFrame(columns=cols)
