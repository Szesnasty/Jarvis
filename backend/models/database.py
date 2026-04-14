import logging

import aiosqlite
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    folder TEXT NOT NULL DEFAULT '',
    content_preview TEXT DEFAULT '',
    body TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    frontmatter TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    indexed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(folder);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, body, tags,
    content='notes',
    content_rowid='id'
);
"""

TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, body, tags)
    VALUES (new.id, new.title, new.body, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)
    VALUES ('delete', old.id, old.title, old.body, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, body, tags)
    VALUES ('delete', old.id, old.title, old.body, old.tags);
    INSERT INTO notes_fts(rowid, title, body, tags)
    VALUES (new.id, new.title, new.body, new.tags);
END;
"""

EMBEDDINGS_SQL = """
CREATE TABLE IF NOT EXISTS note_embeddings (
    note_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    embedding BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    model_name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedded_at TEXT NOT NULL
);
"""


_VALID_TABLES = {"notes"}


async def _column_exists(db, table: str, column: str) -> bool:
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    return any(row[1] == column for row in rows)


async def _fts_indexes_body(db) -> bool:
    cursor = await db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='notes_fts'"
    )
    row = await cursor.fetchone()
    if not row or not row[0]:
        return False
    return " body" in row[0] or "(body" in row[0] or ",body" in row[0]


async def init_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(SCHEMA_SQL)

        if not await _column_exists(db, "notes", "body"):
            await db.execute("ALTER TABLE notes ADD COLUMN body TEXT DEFAULT ''")

        if not await _fts_indexes_body(db):
            # Drop and recreate FTS + triggers atomically in one script
            try:
                await db.executescript(
                    "DROP TRIGGER IF EXISTS notes_ai;"
                    "DROP TRIGGER IF EXISTS notes_au;"
                    "DROP TRIGGER IF EXISTS notes_ad;"
                    "DROP TABLE IF EXISTS notes_fts;"
                )
            except Exception as exc:
                logger.error("Failed to drop old FTS objects: %s", exc)

        try:
            await db.executescript(FTS_SQL + "\n" + TRIGGER_SQL)
        except Exception as exc:
            logger.error("Failed to create FTS table/triggers: %s", exc)

        await db.executescript(EMBEDDINGS_SQL)
        await db.commit()
