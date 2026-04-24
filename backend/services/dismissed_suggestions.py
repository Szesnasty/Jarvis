"""Dismissed suggestions store (Step 25 PR 5).

A small SQLite table that records suggestion pairs the user has explicitly
dropped, so :func:`connection_service.connect_note` never re-proposes them.

Source-of-truth note: this is an operational state table, not user
knowledge — it can be wiped without losing data (the user simply gets
the same suggestions again).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Set, Tuple

logger = logging.getLogger(__name__)

DISMISSED_SUGGESTIONS_SQL = """
CREATE TABLE IF NOT EXISTS dismissed_suggestions (
    note_path    TEXT NOT NULL,
    target_path  TEXT NOT NULL,
    dismissed_at TEXT NOT NULL,
    PRIMARY KEY (note_path, target_path)
);
CREATE INDEX IF NOT EXISTS idx_dismissed_note ON dismissed_suggestions(note_path);
"""


def _ensure_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(DISMISSED_SUGGESTIONS_SQL)
        conn.commit()


def dismiss(db_path: Path, note_path: str, target_path: str) -> None:
    _ensure_table(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO dismissed_suggestions"
            "(note_path, target_path, dismissed_at) VALUES (?, ?, ?)",
            (note_path, target_path, now),
        )
        conn.commit()


def undismiss(db_path: Path, note_path: str, target_path: str) -> None:
    if not db_path.exists():
        return
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "DELETE FROM dismissed_suggestions WHERE note_path = ? AND target_path = ?",
            (note_path, target_path),
        )
        conn.commit()


def list_dismissed_for(db_path: Path, note_path: str) -> Set[str]:
    if not db_path.exists():
        return set()
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(
            "SELECT target_path FROM dismissed_suggestions WHERE note_path = ?",
            (note_path,),
        )
        return {row[0] for row in cursor.fetchall()}


def list_all(db_path: Path) -> Iterable[Tuple[str, str, str]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute(
            "SELECT note_path, target_path, dismissed_at FROM dismissed_suggestions"
        )
        return list(cursor.fetchall())


def remove_note(db_path: Path, note_path: str) -> None:
    """Drop all rows that reference ``note_path`` as either side of the pair."""
    if not db_path.exists():
        return
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "DELETE FROM dismissed_suggestions "
            "WHERE note_path = ? OR target_path = ?",
            (note_path, note_path),
        )
        conn.commit()
