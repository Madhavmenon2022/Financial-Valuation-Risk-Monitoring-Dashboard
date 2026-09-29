"""
Exception Workflow Manager
===========================
Handles analyst workflow state transitions (Open, Under Review, Resolved),
investigation notes entry, bulk status updates, and workflow metrics.
"""

import pandas as pd
from typing import List, Optional, Union, Dict
from pathlib import Path
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import (
    update_exception_status,
    add_analyst_note,
    get_all_exceptions,
    get_audit_trail,
    DB_PATH
)


VALID_STATUSES = ["Open", "Under Review", "Resolved"]


def change_exception_status(
    exception_id: str,
    new_status: str,
    analyst_id: str = "Analyst",
    notes: str = "",
    db_path: Union[str, Path] = DB_PATH
) -> bool:
    """
    Update the workflow status of a single exception.

    Parameters
    ----------
    exception_id : str
        Target exception ID (e.g. 'EXC-POS-00001-MP').
    new_status : str
        Target status ('Open', 'Under Review', 'Resolved').
    analyst_id : str
        ID/Name of the analyst making the change.
    notes : str, optional
        Optional notes explaining the status change.
    db_path : Path, optional
        SQLite database path.

    Returns
    -------
    bool
        True if updated successfully.
    """
    return update_exception_status(exception_id, new_status, analyst_id, notes, db_path)


def bulk_update_status(
    exception_ids: List[str],
    new_status: str,
    analyst_id: str = "Analyst",
    notes: str = "",
    db_path: Union[str, Path] = DB_PATH
) -> int:
    """
    Update the status of multiple exceptions at once.

    Returns
    -------
    int
        Count of successfully updated exceptions.
    """
    count = 0
    for exc_id in exception_ids:
        if update_exception_status(exc_id, new_status, analyst_id, notes, db_path):
            count += 1
    return count


def add_investigation_note(
    exception_id: str,
    note: str,
    analyst_id: str = "Analyst",
    db_path: Union[str, Path] = DB_PATH
) -> bool:
    """Add analyst notes to an exception."""
    return add_analyst_note(exception_id, note, analyst_id, db_path)


def get_persisted_exceptions(db_path: Union[str, Path] = DB_PATH) -> pd.DataFrame:
    """Retrieve all exceptions from the SQLite database."""
    return get_all_exceptions(db_path)


def get_workflow_kpis(db_path: Union[str, Path] = DB_PATH) -> Dict[str, int]:
    """Calculate key workflow status metrics."""
    df = get_all_exceptions(db_path)
    if len(df) == 0:
        return {
            "total": 0,
            "open": 0,
            "under_review": 0,
            "resolved": 0,
            "resolution_rate_pct": 0.0,
        }

    total = len(df)
    counts = df["status"].value_counts().to_dict()
    open_c = counts.get("Open", 0)
    review_c = counts.get("Under Review", 0)
    res_c = counts.get("Resolved", 0)
    res_rate = round((res_c / total) * 100, 1) if total > 0 else 0.0

    return {
        "total": total,
        "open": open_c,
        "under_review": review_c,
        "resolved": res_c,
        "resolution_rate_pct": res_rate,
    }
