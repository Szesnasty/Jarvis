import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite

from config import get_settings
from models.database import init_database
from utils.markdown import add_frontmatter, parse_frontmatter


class NoteNotFoundError(Exception):
    pass


class NoteExistsError(Exception):
    pass


def _memory_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _db_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"


def _trash_path(workspace_path: Optional[Path] = None) -> Path:
    path = (workspace_path or get_settings().workspace_path) / ".trash"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_path(note_path: str) -> None:
    """Prevent path traversal attacks."""
    normalized = Path(note_path).as_posix()
    if ".." in normalized or normalized.startswith("/"):
        raise ValueError("Invalid path: path traversal not allowed")


async def create_note(
    note_path: str,
    content: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    _validate_path(note_path)
    mem = _memory_path(workspace_path)
    db_p = _db_path(workspace_path)

    if not note_path.endswith(".md"):
        note_path = note_path + ".md"

    file_path = mem / note_path
    if file_path.exists():
        raise NoteExistsError(f"Note already exists: {note_path}")

    # Parse or create frontmatter
    fm, body = parse_frontmatter(content)
    now = datetime.now(timezone.utc).isoformat()
    if "title" not in fm:
        fm["title"] = Path(note_path).stem.replace("-", " ").replace("_", " ").title()
    if "created_at" not in fm:
        fm["created_at"] = now
    if "tags" not in fm:
        fm["tags"] = []
    fm["updated_at"] = now

    full_content = add_frontmatter(body, fm)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(full_content, encoding="utf-8")

    await _index_note(note_path, full_content, fm, body, db_p)

    return _note_metadata(note_path, fm, body)


async def get_note(
    note_path: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    _validate_path(note_path)
    mem = _memory_path(workspace_path)
    file_path = mem / note_path

    if not file_path.exists():
        raise NoteNotFoundError(f"Note not found: {note_path}")

    content = file_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    
    # Convert any non-JSON-serializable objects in frontmatter
    for key, value in fm.items():
        if hasattr(value, 'isoformat'):  # datetime objects
            fm[key] = value.isoformat()
        elif isinstance(value, list):
            fm[key] = [str(v) if hasattr(v, 'isoformat') else v for v in value]

    return {
        "path": note_path,
        "title": fm.get("title", Path(note_path).stem),
        "content": content,
        "frontmatter": fm,
        "updated_at": str(fm.get("updated_at", "")),
    }


async def list_notes(
    folder: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    workspace_path: Optional[Path] = None,
) -> List[Dict]:
    db_p = _db_path(workspace_path)

    if not db_p.exists():
        return []

    async with aiosqlite.connect(str(db_p)) as db:
        db.row_factory = aiosqlite.Row
        if search:
            query = """
                SELECT n.path, n.title, n.folder, n.tags, n.updated_at, n.word_count
                FROM notes n
                JOIN notes_fts f ON n.id = f.rowid
                WHERE notes_fts MATCH ?
            """
            params: list = [search + "*"]
            if folder:
                query += " AND n.folder = ?"
                params.append(folder)
            query += " ORDER BY rank LIMIT ?"
            params.append(limit)
            cursor = await db.execute(query, params)
        else:
            query = "SELECT path, title, folder, tags, updated_at, word_count FROM notes"
            params = []
            if folder:
                query += " WHERE folder = ?"
                params.append(folder)
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            cursor = await db.execute(query, params)

        rows = await cursor.fetchall()
        return [
            {
                "path": row["path"],
                "title": row["title"],
                "folder": row["folder"],
                "tags": json.loads(row["tags"]),
                "updated_at": row["updated_at"],
                "word_count": row["word_count"],
            }
            for row in rows
        ]


async def append_note(
    note_path: str,
    append_text: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    _validate_path(note_path)
    mem = _memory_path(workspace_path)
    db_p = _db_path(workspace_path)
    file_path = mem / note_path

    if not file_path.exists():
        raise NoteNotFoundError(f"Note not found: {note_path}")

    content = file_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    now = datetime.now(timezone.utc).isoformat()
    fm["updated_at"] = now

    new_body = body + append_text
    full_content = add_frontmatter(new_body, fm)
    file_path.write_text(full_content, encoding="utf-8")

    await _index_note(note_path, full_content, fm, new_body, db_p)

    return _note_metadata(note_path, fm, new_body)


async def delete_note(
    note_path: str,
    workspace_path: Optional[Path] = None,
) -> None:
    _validate_path(note_path)
    mem = _memory_path(workspace_path)
    db_p = _db_path(workspace_path)
    file_path = mem / note_path

    if not file_path.exists():
        raise NoteNotFoundError(f"Note not found: {note_path}")

    trash = _trash_path(workspace_path)
    dest = trash / note_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(file_path), str(dest))

    if db_p.exists():
        async with aiosqlite.connect(str(db_p)) as db:
            await db.execute("DELETE FROM notes WHERE path = ?", (note_path,))
            await db.commit()


async def index_note_file(
    note_path: str,
    workspace_path: Optional[Path] = None,
) -> None:
    _validate_path(note_path)
    mem = _memory_path(workspace_path)
    db_p = _db_path(workspace_path)
    file_path = mem / note_path

    if not file_path.exists():
        raise NoteNotFoundError(f"Note not found: {note_path}")

    content = file_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    await _index_note(note_path, content, fm, body, db_p)


async def reindex_all(workspace_path: Optional[Path] = None) -> int:
    mem = _memory_path(workspace_path)
    db_p = _db_path(workspace_path)

    await init_database(db_p)

    async with aiosqlite.connect(str(db_p)) as db:
        await db.execute("DELETE FROM notes")
        await db.commit()

    count = 0
    if mem.exists():
        for md_file in mem.rglob("*.md"):
            rel = md_file.relative_to(mem).as_posix()
            content = md_file.read_text(encoding="utf-8")
            fm, body = parse_frontmatter(content)
            await _index_note(rel, content, fm, body, db_p)
            count += 1

    return count


async def _index_note(
    note_path: str,
    full_content: str,
    fm: Dict,
    body: str,
    db_path: Path,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    folder = str(Path(note_path).parent) if "/" in note_path else ""
    tags = json.dumps(fm.get("tags", []), default=str)
    preview = body[:200].strip()
    word_count = len(body.split())

    await init_database(db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            """
            INSERT INTO notes (path, title, folder, content_preview, body, tags, frontmatter,
                              created_at, updated_at, word_count, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title,
                folder=excluded.folder,
                content_preview=excluded.content_preview,
                body=excluded.body,
                tags=excluded.tags,
                frontmatter=excluded.frontmatter,
                updated_at=excluded.updated_at,
                word_count=excluded.word_count,
                indexed_at=excluded.indexed_at
            """,
            (
                note_path,
                fm.get("title", Path(note_path).stem),
                folder,
                preview,
                body,
                tags,
                json.dumps(fm, default=str),
                fm.get("created_at", now),
                fm.get("updated_at", now),
                word_count,
                now,
            ),
        )
        await db.commit()


def _note_metadata(note_path: str, fm: Dict, body: str) -> Dict:
    return {
        "path": note_path,
        "title": fm.get("title", Path(note_path).stem),
        "folder": str(Path(note_path).parent) if "/" in note_path else "",
        "tags": fm.get("tags", []),
        "updated_at": fm.get("updated_at", ""),
        "word_count": len(body.split()),
    }
