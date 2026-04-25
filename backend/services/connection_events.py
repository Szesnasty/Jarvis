"""Connection event log — Step 26c.

Analytics-only table recording promote / dismiss / backfill_suggested events.
The dismissed_suggestions table remains the canonical dedup store for the
pipeline; this module is for metrics and acceptance-rate tracking only.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

CONNECTION_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS connection_events (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type             TEXT NOT NULL,
    note_path              TEXT NOT NULL,
    target_path            TEXT,
    confidence             REAL,
    methods_json           TEXT,
    tier                   TEXT,
    smart_connect_version  INTEGER,
    created_at             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_connection_events_type_created
  ON connection_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_connection_events_note
  ON connection_events(note_path);
"""


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_event(
    db_path: Path,
    *,
    event_type: str,
    note_path: str,
    target_path: Optional[str] = None,
    confidence: Optional[float] = None,
    methods: Optional[List[str]] = None,
    tier: Optional[str] = None,
    smart_connect_version: Optional[int] = None,
) -> None:
    """Append one row to ``connection_events``.

    Silently no-ops when the DB is unavailable; analytics writes must never
    block or fail note operations.
    """
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            # Wait up to 5 s for concurrent writers (backfill loop + worker).
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.executescript(CONNECTION_EVENTS_SQL)  # idempotent CREATE IF NOT EXISTS
            conn.execute(
                "INSERT INTO connection_events"
                " (event_type, note_path, target_path, confidence,"
                "  methods_json, tier, smart_connect_version, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_type,
                    note_path,
                    target_path,
                    confidence,
                    json.dumps(methods) if methods is not None else None,
                    tier,
                    smart_connect_version,
                    _now_utc(),
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("connection_events write failed: %s", exc)


def backfill_suggested_dedup_key_exists(
    db_path: Path,
    *,
    note_path: str,
    target_path: str,
    smart_connect_version: int,
    today: str,
) -> bool:
    """Return True if a backfill_suggested row for this (note, target, version) exists today."""
    try:
        if not db_path.exists():
            return False
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA busy_timeout = 5000")
            row = conn.execute(
                "SELECT 1 FROM connection_events"
                " WHERE event_type = 'backfill_suggested'"
                "   AND note_path = ?"
                "   AND target_path = ?"
                "   AND smart_connect_version = ?"
                "   AND created_at LIKE ? || '%'"
                " LIMIT 1",
                (note_path, target_path, smart_connect_version, today),
            ).fetchone()
            return row is not None
    except Exception as exc:
        logger.warning("connection_events dedup check failed: %s", exc)
        return False
