"""
Database & Audit Trail Manager (SQLite)
========================================
Manages persistent exception storage, analyst workflow statuses (Open, Under Review, Resolved),
analyst investigation notes, and immutable audit logs.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import DB_PATH


def get_connection(db_path: Union[str, Path] = DB_PATH) -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Union[str, Path] = DB_PATH) -> None:
    """Initialize the SQLite database schema if tables do not exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Table for exceptions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exceptions (
        exception_id TEXT PRIMARY KEY,
        position_id TEXT,
        instrument_id TEXT,
        asset_class TEXT,
        counterparty TEXT,
        currency TEXT,
        quantity REAL,
        recorded_price REAL,
        reference_price REAL,
        percentage_diff REAL,
        exception_type TEXT,
        severity TEXT,
        reason TEXT,
        status TEXT DEFAULT 'Open',
        analyst_notes TEXT DEFAULT '',
        assigned_to TEXT DEFAULT '',
        created_at TEXT,
        updated_at TEXT,
        resolved_at TEXT
    )
    """)

    # Table for audit logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        exception_id TEXT,
        action TEXT,
        previous_state TEXT,
        new_state TEXT,
        analyst_id TEXT,
        notes TEXT
    )
    """)

    conn.commit()
    conn.close()


def sync_exceptions(df: pd.DataFrame, db_path: Union[str, Path] = DB_PATH) -> pd.DataFrame:
    """
    Synchronize detected exceptions with SQLite database.

    - Preserves existing exception status, analyst notes, and timestamps.
    - Inserts new exceptions with status='Open' and logs creation in audit_logs.
    - Returns a DataFrame enriched with persistent status, notes, and timestamps.
    """
    init_db(db_path)
    if df is None or len(df) == 0:
        return pd.DataFrame()

    conn = get_connection(db_path)
    cursor = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    enriched_rows = []

    for _, row in df.iterrows():
        exc_id = str(row.get("exception_id", ""))
        if not exc_id:
            continue

        # Check if exception already exists in DB
        cursor.execute("SELECT * FROM exceptions WHERE exception_id = ?", (exc_id,))
        existing = cursor.fetchone()

        pos_id = str(row.get("position_id", ""))
        inst_id = str(row.get("instrument_id", ""))
        asset = str(row.get("asset_class", ""))
        cp = str(row.get("counterparty", ""))
        curr = str(row.get("currency", ""))
        qty = float(row.get("quantity", 0)) if pd.notna(row.get("quantity")) else None
        rec_p = float(row.get("recorded_price", 0)) if pd.notna(row.get("recorded_price")) else None
        ref_p = float(row.get("reference_price", 0)) if pd.notna(row.get("reference_price")) else None
        pct_diff = float(row.get("percentage_diff", 0)) if pd.notna(row.get("percentage_diff")) else None
        exc_type = str(row.get("exception_type", ""))
        sev = str(row.get("severity", ""))
        reas = str(row.get("reason", ""))

        if existing:
            # Preserve existing status, notes, created_at, resolved_at
            status = existing["status"]
            notes = existing["analyst_notes"] or ""
            assigned = existing["assigned_to"] or ""
            created_at = existing["created_at"]
            resolved_at = existing["resolved_at"]
            updated_at = now_str

            # Update metrics in DB if re-detected
            cursor.execute("""
            UPDATE exceptions SET
                recorded_price = ?, reference_price = ?, percentage_diff = ?,
                severity = ?, reason = ?, updated_at = ?
            WHERE exception_id = ?
            """, (rec_p, ref_p, pct_diff, sev, reas, updated_at, exc_id))
        else:
            # Insert new exception
            status = "Open"
            notes = ""
            assigned = ""
            created_at = now_str
            updated_at = now_str
            resolved_at = None

            cursor.execute("""
            INSERT INTO exceptions (
                exception_id, position_id, instrument_id, asset_class, counterparty, currency,
                quantity, recorded_price, reference_price, percentage_diff, exception_type,
                severity, reason, status, analyst_notes, assigned_to, created_at, updated_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exc_id, pos_id, inst_id, asset, cp, curr,
                qty, rec_p, ref_p, pct_diff, exc_type,
                sev, reas, status, notes, assigned, created_at, updated_at, resolved_at
            ))

            # Audit log entry for creation
            cursor.execute("""
            INSERT INTO audit_logs (timestamp, exception_id, action, previous_state, new_state, analyst_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now_str, exc_id, "EXCEPTION_CREATED", "", "Open", "System", f"Detected exception {exc_type}"))

        row_dict = dict(row)
        row_dict["status"] = status
        row_dict["analyst_notes"] = notes
        row_dict["assigned_to"] = assigned
        row_dict["created_at"] = created_at
        row_dict["updated_at"] = updated_at
        row_dict["resolved_at"] = resolved_at
        enriched_rows.append(row_dict)

    conn.commit()
    conn.close()

    return pd.DataFrame(enriched_rows)


def update_exception_status(
    exception_id: str,
    new_status: str,
    analyst_id: str = "System",
    notes: str = "",
    db_path: Union[str, Path] = DB_PATH
) -> bool:
    """
    Update the status of an exception ('Open', 'Under Review', 'Resolved').
    Logs the state transition in audit_logs.
    """
    valid_statuses = ["Open", "Under Review", "Resolved"]
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}")

    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT status, analyst_notes FROM exceptions WHERE exception_id = ?", (exception_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    prev_status = row["status"]
    if prev_status == new_status and not notes:
        conn.close()
        return True

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resolved_at = now_str if new_status == "Resolved" else None

    # Update notes if provided
    current_notes = row["analyst_notes"] or ""
    if notes:
        timestamp_note = f"[{now_str} - {analyst_id}]: {notes}"
        updated_notes = f"{current_notes}\n{timestamp_note}".strip() if current_notes else timestamp_note
    else:
        updated_notes = current_notes

    cursor.execute("""
    UPDATE exceptions SET
        status = ?,
        analyst_notes = ?,
        updated_at = ?,
        resolved_at = CASE WHEN ? = 'Resolved' THEN ? ELSE resolved_at END
    WHERE exception_id = ?
    """, (new_status, updated_notes, now_str, new_status, resolved_at, exception_id))

    # Log in audit trail
    action_str = f"STATUS_CHANGE ({prev_status} -> {new_status})"
    cursor.execute("""
    INSERT INTO audit_logs (timestamp, exception_id, action, previous_state, new_state, analyst_id, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now_str, exception_id, action_str, prev_status, new_status, analyst_id, notes or f"Status changed to {new_status}"))

    conn.commit()
    conn.close()
    return True


def add_analyst_note(
    exception_id: str,
    note: str,
    analyst_id: str = "Analyst",
    db_path: Union[str, Path] = DB_PATH
) -> bool:
    """Append investigation notes to an exception and record in audit log."""
    if not note or not note.strip():
        return False

    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT analyst_notes, status FROM exceptions WHERE exception_id = ?", (exception_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    current_notes = row["analyst_notes"] or ""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_note = f"[{now_str} - {analyst_id}]: {note.strip()}"
    updated_notes = f"{current_notes}\n{timestamp_note}".strip() if current_notes else timestamp_note

    cursor.execute("""
    UPDATE exceptions SET analyst_notes = ?, updated_at = ? WHERE exception_id = ?
    """, (updated_notes, now_str, exception_id))

    cursor.execute("""
    INSERT INTO audit_logs (timestamp, exception_id, action, previous_state, new_state, analyst_id, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now_str, exception_id, "NOTE_ADDED", row["status"], row["status"], analyst_id, note.strip()))

    conn.commit()
    conn.close()
    return True


def get_all_exceptions(db_path: Union[str, Path] = DB_PATH) -> pd.DataFrame:
    """Retrieve all persisted exceptions from SQLite database."""
    init_db(db_path)
    conn = get_connection(db_path)
    df = pd.read_sql_query("SELECT * FROM exceptions ORDER BY created_at DESC", conn)
    conn.close()
    return df


def get_audit_trail(
    exception_id: Optional[str] = None,
    limit: int = 500,
    db_path: Union[str, Path] = DB_PATH
) -> pd.DataFrame:
    """Retrieve audit trail logs filtered by exception_id or recent activity."""
    init_db(db_path)
    conn = get_connection(db_path)
    if exception_id:
        query = "SELECT * FROM audit_logs WHERE exception_id = ? ORDER BY log_id DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(exception_id, limit))
    else:
        query = "SELECT * FROM audit_logs ORDER BY log_id DESC LIMIT ?"
        df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    return df


def clear_db(db_path: Union[str, Path] = DB_PATH) -> None:
    """Clear all tables in SQLite database (for testing purposes)."""
    if Path(db_path).exists():
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS exceptions")
        cursor.execute("DROP TABLE IF EXISTS audit_logs")
        conn.commit()
        conn.close()
