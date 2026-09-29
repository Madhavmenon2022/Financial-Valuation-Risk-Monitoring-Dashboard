"""
Unit tests for Database & Audit Trail Manager (src/database.py and src/exception_workflow.py).
Tests SQLite database creation, exception status transitions, analyst notes, and audit logging.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import os

from src.database import (
    init_db,
    sync_exceptions,
    update_exception_status,
    add_analyst_note,
    get_all_exceptions,
    get_audit_trail,
    clear_db,
)
from src.exception_workflow import (
    change_exception_status,
    bulk_update_status,
    get_workflow_kpis,
)


@pytest.fixture
def temp_db_path(tmp_path):
    db_file = tmp_path / "test_audit_trail.db"
    init_db(db_file)
    yield db_file
    if db_file.exists():
        clear_db(db_file)


@pytest.fixture
def sample_exceptions_df():
    return pd.DataFrame([
        {
            "exception_id": "EXC-POS-00001-MP",
            "position_id": "POS-00001",
            "instrument_id": "EQ-AAPL-001",
            "asset_class": "Equity",
            "counterparty": "GlobalBank",
            "currency": "USD",
            "quantity": 100,
            "recorded_price": None,
            "reference_price": 150.0,
            "percentage_diff": None,
            "exception_type": "Missing Price",
            "severity": "Critical",
            "reason": "Recorded price is missing",
        },
        {
            "exception_id": "EXC-POS-00002-TB",
            "position_id": "POS-00002",
            "instrument_id": "FI-BOND-002",
            "asset_class": "Fixed Income",
            "counterparty": "Apex Trading",
            "currency": "USD",
            "quantity": 1000,
            "recorded_price": 90.0,
            "reference_price": 100.0,
            "percentage_diff": 10.0,
            "exception_type": "Threshold Breach",
            "severity": "Critical",
            "reason": "Valuation difference of 10.00% exceeds threshold",
        },
    ])


class TestDatabaseAndAuditTrail:
    def test_init_db(self, temp_db_path):
        assert temp_db_path.exists()
        df_exc = get_all_exceptions(temp_db_path)
        df_audit = get_audit_trail(db_path=temp_db_path)
        assert len(df_exc) == 0
        assert len(df_audit) == 0

    def test_sync_exceptions_creates_records(self, temp_db_path, sample_exceptions_df):
        synced = sync_exceptions(sample_exceptions_df, db_path=temp_db_path)
        assert len(synced) == 2
        assert "status" in synced.columns
        assert (synced["status"] == "Open").all()

        # Verify DB records
        from_db = get_all_exceptions(temp_db_path)
        assert len(from_db) == 2

        # Verify audit logs created
        logs = get_audit_trail(db_path=temp_db_path)
        assert len(logs) == 2
        assert set(logs["action"]) == {"EXCEPTION_CREATED"}

    def test_status_transition_workflow(self, temp_db_path, sample_exceptions_df):
        sync_exceptions(sample_exceptions_df, db_path=temp_db_path)
        exc_id = "EXC-POS-00001-MP"

        # Update status to Under Review
        success = update_exception_status(
            exc_id, "Under Review", analyst_id="Analyst_1", notes="Investigating pricing feed issue", db_path=temp_db_path
        )
        assert success is True

        from_db = get_all_exceptions(temp_db_path)
        row = from_db[from_db["exception_id"] == exc_id].iloc[0]
        assert row["status"] == "Under Review"
        assert "Investigating pricing feed issue" in row["analyst_notes"]

        # Update status to Resolved
        success2 = update_exception_status(
            exc_id, "Resolved", analyst_id="Analyst_2", notes="Manual price override confirmed", db_path=temp_db_path
        )
        assert success2 is True

        from_db2 = get_all_exceptions(temp_db_path)
        row2 = from_db2[from_db2["exception_id"] == exc_id].iloc[0]
        assert row2["status"] == "Resolved"
        assert row2["resolved_at"] is not None

        # Verify audit log history
        logs = get_audit_trail(exception_id=exc_id, db_path=temp_db_path)
        assert len(logs) == 3  # 1 Created + 2 Status Changes

    def test_add_analyst_note(self, temp_db_path, sample_exceptions_df):
        sync_exceptions(sample_exceptions_df, db_path=temp_db_path)
        exc_id = "EXC-POS-00002-TB"

        added = add_analyst_note(
            exc_id, "Emailed counterparty for trade confirmation", analyst_id="Risk_Analyst", db_path=temp_db_path
        )
        assert added is True

        from_db = get_all_exceptions(temp_db_path)
        row = from_db[from_db["exception_id"] == exc_id].iloc[0]
        assert "Emailed counterparty for trade confirmation" in row["analyst_notes"]

        logs = get_audit_trail(exception_id=exc_id, db_path=temp_db_path)
        assert any(l == "NOTE_ADDED" for l in logs["action"])

    def test_bulk_status_update(self, temp_db_path, sample_exceptions_df):
        sync_exceptions(sample_exceptions_df, db_path=temp_db_path)
        ids = ["EXC-POS-00001-MP", "EXC-POS-00002-TB"]

        count = bulk_update_status(ids, "Under Review", analyst_id="Bulk_Lead", db_path=temp_db_path)
        assert count == 2

        kpis = get_workflow_kpis(temp_db_path)
        assert kpis["under_review"] == 2
        assert kpis["open"] == 0

    def test_invalid_status_raises_error(self, temp_db_path, sample_exceptions_df):
        sync_exceptions(sample_exceptions_df, db_path=temp_db_path)
        with pytest.raises(ValueError):
            update_exception_status("EXC-POS-00001-MP", "Closed", db_path=temp_db_path)
