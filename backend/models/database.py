import aiosqlite
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    folder TEXT NOT NULL DEFAULT '',
    content_preview TEXT DEFAULT '',
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
    title, content_preview, tags,
    content='notes',
    content_rowid='id'
);
"""

TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts(rowid, title, content_preview, tags)
    VALUES (new.id, new.title, new.content_preview, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content_preview, tags)
    VALUES ('delete', old.id, old.title, old.content_preview, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts(notes_fts, rowid, title, content_preview, tags)
    VALUES ('delete', old.id, old.title, old.content_preview, old.tags);
    INSERT INTO notes_fts(rowid, title, content_preview, tags)
    VALUES (new.id, new.title, new.content_preview, new.tags);
END;
"""


async def init_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(SCHEMA_SQL)
        # FTS and triggers must be created separately — executescript may not handle them in one batch
        try:
            await db.executescript(FTS_SQL)
        except Exception:
            pass  # Already exists
        try:
            await db.executescript(TRIGGER_SQL)
        except Exception:
            pass  # Already exists
        await db.commit()
