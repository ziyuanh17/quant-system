"""SQLite database for historical observability.

Stores time-series status observations, events, and reconciliation
results. Provides simple query interfaces for the historical
observability page.

"""

import sqlite3
from pathlib import Path

_DB_PATH = Path("data/web/console.db")


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection, creating the database if needed."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS status_observation (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             observed_at TEXT NOT NULL,
             source TEXT NOT NULL,
             state TEXT NOT NULL,
             severity TEXT NOT NULL,
             message TEXT,
             age_seconds INTEGER,
             is_stale INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS event (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             timestamp TEXT NOT NULL,
             event_type TEXT NOT NULL,
             component TEXT NOT NULL,
             status TEXT NOT NULL,
             message TEXT,
             workflow_id TEXT,
             evidence_ref TEXT
        );

        CREATE TABLE IF NOT EXISTS reconciliation (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             observed_at TEXT NOT NULL,
             environment TEXT NOT NULL,
             status TEXT NOT NULL,
             difference_count INTEGER DEFAULT 0,
             details TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_status_observed
             ON status_observation(observed_at);
        CREATE INDEX IF NOT EXISTS idx_event_timestamp
             ON event(timestamp);
        CREATE INDEX IF NOT EXISTS idx_recon_observed
             ON reconciliation(observed_at);
    """)
