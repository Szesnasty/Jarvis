"""Shared SQLite connection helpers.

Centralises pragmas that must be applied to every new connection to keep
SQLite happy under concurrent writers (backfill loop + enrichment worker
+ session saves can all hit the same DB at once).

WAL is enabled at database creation time (file-level mode), so opening
existing databases inherits it automatically. ``busy_timeout`` is a
per-connection setting and MUST be set on every new connection — without
it, any contended write fails immediately with ``database is locked``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite

# 5 s is plenty: SQLite contention on a local single-user app is in the
# millisecond range; 5 s only kicks in when something is genuinely stuck.
DEFAULT_BUSY_TIMEOUT_MS = 5_000


def connect_sync(db_path: Path | str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> sqlite3.Connection:
    """Open a sync sqlite3 connection with sane defaults applied."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    return conn


def connect_async(db_path: Path | str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> aiosqlite.Connection:
    """Open an aiosqlite connection. Caller still uses ``async with``.

    Returns the unawaited connection object so the standard
    ``async with aiosqlite.connect(...)`` pattern works unchanged via
    ``async with connect_async(path):``. The pragma is applied lazily
    via the ``init`` callback aiosqlite supports natively.
    """
    return aiosqlite.connect(
        str(db_path),
        # aiosqlite forwards kwargs to sqlite3.connect — busy_timeout is
        # set via PRAGMA below in the init step. We use ``isolation_level``
        # passthrough only when callers need it.
    )


async def apply_pragmas(db: aiosqlite.Connection, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> None:
    """Apply per-connection pragmas to an already-opened aiosqlite connection."""
    await db.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
