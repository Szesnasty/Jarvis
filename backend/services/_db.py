"""Shared SQLite connection helpers.

Centralises pragmas that must be applied to every new connection to keep
SQLite happy under concurrent writers (backfill loop + enrichment worker
+ session saves + heavy ingest of large PDFs can all hit the same DB at
once).

WAL is enabled at database creation time (file-level mode) and persists
across opens automatically. ``busy_timeout`` and ``synchronous`` are
per-connection settings and MUST be applied on every new connection —
without them, any contended write fails immediately with
``database is locked``.

Use ``open_db(path)`` as a drop-in replacement for
``aiosqlite.connect(str(path))`` whenever you write to the DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite

# 30 s. Heavy ingest of large PDFs (200 MB+ → thousands of chunk inserts +
# embeddings) can hold short bursts of write locks well beyond 5 s. This
# only kicks in when something is contended; idle waits cost nothing.
DEFAULT_BUSY_TIMEOUT_MS = 30_000


def connect_sync(db_path: Path | str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> sqlite3.Connection:
    """Open a sync sqlite3 connection with sane defaults applied."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


async def apply_pragmas(db: aiosqlite.Connection, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> None:
    """Apply per-connection pragmas to an already-opened aiosqlite connection.

    - ``busy_timeout`` — wait up to N ms for a contended write lock instead of
      failing instantly with ``database is locked``.
    - ``synchronous = NORMAL`` — safe under WAL; massively reduces fsync
      overhead during bulk ingest (chunk embeddings of large PDFs).
    """
    await db.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    await db.execute("PRAGMA synchronous = NORMAL")


class _PragmaConnect:
    """Async context-manager wrapper that applies pragmas right after open."""

    __slots__ = ("_factory", "_conn", "_busy_timeout_ms")

    def __init__(self, db_path: Path | str, busy_timeout_ms: int) -> None:
        self._factory = aiosqlite.connect(str(db_path))
        self._conn: aiosqlite.Connection | None = None
        self._busy_timeout_ms = busy_timeout_ms

    async def __aenter__(self) -> aiosqlite.Connection:
        self._conn = await self._factory.__aenter__()
        await apply_pragmas(self._conn, busy_timeout_ms=self._busy_timeout_ms)
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return await self._factory.__aexit__(exc_type, exc, tb)


def open_db(db_path: Path | str, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> _PragmaConnect:
    """Drop-in for ``aiosqlite.connect(str(path))`` with pragmas applied.

    Usage::

        async with open_db(db_path) as db:
            await db.execute(...)
            await db.commit()
    """
    return _PragmaConnect(db_path, busy_timeout_ms)
