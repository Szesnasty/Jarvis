import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite

from config import get_settings
from models.database import init_database
from utils.markdown import add_frontmatter, parse_frontmatter

logger = logging.getLogger(__name__)


def _sanitize_for_log(value: object) -> str:
    return str(value).replace("\r", "").replace("\n", "")


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


def _validate_path(note_path: str, base: Optional[Path] = None) -> None:
    """Prevent path traversal attacks.

    Uses resolve() + relative_to() containment check to block all traversal
    patterns including Windows absolute paths and encoded sequences.
    """
    normalized = Path(note_path).as_posix()
    if ".." in normalized or normalized.startswith("/"):
        raise ValueError("Invalid path: path traversal not allowed")
    # Additional containment check when base is provided
    if base is not None:
        try:
            resolved = (base / note_path).resolve()
            base_resolved = base.resolve()
            resolved.relative_to(base_resolved)
        except (ValueError, OSError):
            raise ValueError("Invalid path: path traversal not allowed")
    # Block Windows absolute paths (e.g. C:\, D:/)
    if len(note_path) >= 2 and note_path[1] == ':':
        raise ValueError("Invalid path: absolute paths not allowed")


async def create_note(
    note_path: str,
    content: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    mem = _memory_path(workspace_path)
    _validate_path(note_path, mem)
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
    mem = _memory_path(workspace_path)
    _validate_path(note_path, mem)
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
            # sanitize: extract word tokens to avoid FTS5 syntax errors from punctuation
            tokens = re.findall(r'\w+', search)[:8]
            if not tokens:
                return []

            # Column weights: title 10×, body 1×, tags 5×
            bm25_expr = "bm25(notes_fts, 10.0, 1.0, 5.0)"

            # Try AND first (all terms required)
            fts_and = " ".join(t + "*" for t in tokens)

            folder_clause = ""
            params: list = [fts_and]
            if folder:
                folder_clause = " AND n.folder = ?"
                params.append(folder)
            params.append(limit)

            # bm25() returns negative values; lower = better match
            query = f"""
                SELECT n.path, n.title, n.folder, n.tags,
                       n.updated_at, n.word_count,
                       {bm25_expr} AS bm25_score
                FROM notes n
                JOIN notes_fts ON notes_fts.rowid = n.id
                WHERE notes_fts MATCH ?{folder_clause}
                ORDER BY bm25_score
                LIMIT ?
            """
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            # Fallback to OR if AND returns < 3 results and we have 2+ tokens
            if len(rows) < 3 and len(tokens) >= 2:
                fts_or = " OR ".join(t + "*" for t in tokens)
                params[0] = fts_or
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
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

        results = []
        for row in rows:
            try:
                tags = json.loads(row["tags"])
            except (json.JSONDecodeError, TypeError):
                tags = []
            item = {
                "path": row["path"],
                "title": row["title"],
                "folder": row["folder"],
                "tags": tags,
                "updated_at": row["updated_at"],
                "word_count": row["word_count"],
            }
            # Include BM25 score for downstream retrieval scoring
            if search:
                item["_bm25_score"] = row["bm25_score"]
            results.append(item)
        return results


async def append_note(
    note_path: str,
    append_text: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    mem = _memory_path(workspace_path)
    _validate_path(note_path, mem)
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
    mem = _memory_path(workspace_path)
    _validate_path(note_path, mem)
    db_p = _db_path(workspace_path)
    file_path = mem / note_path

    file_exists = file_path.exists()

    # Check that either the file or a DB entry exists
    has_db_entry = False
    if db_p.exists():
        async with aiosqlite.connect(str(db_p)) as db:
            cursor = await db.execute("SELECT 1 FROM notes WHERE path = ?", (note_path,))
            has_db_entry = await cursor.fetchone() is not None

    if not file_exists and not has_db_entry:
        raise NoteNotFoundError(f"Note not found: {note_path}")

    # Move file to trash if it exists on disk
    if file_exists:
        trash = _trash_path(workspace_path)
        dest = trash / note_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(dest))

    # Always clean up the DB entry
    if db_p.exists():
        async with aiosqlite.connect(str(db_p)) as db:
            await db.execute("DELETE FROM notes WHERE path = ?", (note_path,))
            await db.execute("DELETE FROM note_embeddings WHERE path = ?", (note_path,))
            await db.execute("DELETE FROM chunk_embeddings WHERE path = ?", (note_path,))
            await db.execute("DELETE FROM note_chunks WHERE path = ?", (note_path,))
            await db.execute("DELETE FROM alias_index WHERE note_path = ?", (note_path,))
            await db.commit()

    # Invalidate graph cache so it rebuilds without the deleted note
    from services.graph_service import invalidate_cache
    invalidate_cache()


async def index_note_file(
    note_path: str,
    workspace_path: Optional[Path] = None,
) -> None:
    mem = _memory_path(workspace_path)
    _validate_path(note_path, mem)
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

    count = 0
    async with aiosqlite.connect(str(db_p)) as db:
        await db.execute("DELETE FROM notes")
        if mem.exists():
            for md_file in mem.rglob("*.md"):
                rel = md_file.relative_to(mem).as_posix()
                content = md_file.read_text(encoding="utf-8")
                fm, body = parse_frontmatter(content)
                now = datetime.now(timezone.utc).isoformat()
                folder = str(Path(rel).parent) if "/" in rel else ""
                tags = json.dumps(fm.get("tags", []), default=str)
                preview = body[:200].strip()
                word_count = len(body.split())
                await db.execute(
                    """
                    INSERT INTO notes (path, title, folder, content_preview, body, tags, frontmatter,
                                      created_at, updated_at, word_count, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        title=excluded.title, folder=excluded.folder,
                        content_preview=excluded.content_preview, body=excluded.body,
                        tags=excluded.tags, frontmatter=excluded.frontmatter,
                        updated_at=excluded.updated_at, word_count=excluded.word_count,
                        indexed_at=excluded.indexed_at
                    """,
                    (
                        rel, fm.get("title", Path(rel).stem), folder, preview, body,
                        tags, json.dumps(fm, default=str),
                        fm.get("created_at", now), fm.get("updated_at", now),
                        word_count, now,
                    ),
                )
                count += 1
        await db.commit()

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
        from services._db import apply_pragmas
        await apply_pragmas(db)
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

    # Step 25 PR 3: maintain alias_index for Smart Connect.
    try:
        from services.alias_index import upsert_note_aliases
        import re as _re
        title = fm.get("title") or Path(note_path).stem
        aliases = fm.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        # Step 26b: honour weak_aliases frontmatter field.
        weak_aliases = fm.get("weak_aliases") or []
        if not isinstance(weak_aliases, list):
            weak_aliases = []
        headings = [h.rstrip() for h in _re.findall(r"^#{1,6}\s+(.+)", body, flags=_re.MULTILINE)]
        upsert_note_aliases(
            db_path,
            note_path,
            title=title,
            aliases=aliases,
            headings=headings,
            weak_aliases=weak_aliases,
        )
    except Exception as exc:
        logger.warning("alias_index upsert failed for %s: %s",
                       _sanitize_for_log(note_path), exc)

    # Auto-embed for semantic search (skip if fastembed missing or disabled)
    import os
    if os.environ.get("JARVIS_DISABLE_EMBEDDINGS") != "1":
        try:
            from services.embedding_service import embed_note
            await embed_note(note_path, full_content, db_path)
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("embed_note failed for %s: %s",
                           _sanitize_for_log(note_path), exc)

        # Auto-embed chunks for chunk-level semantic search
        try:
            from services.embedding_service import embed_note_chunks
            await embed_note_chunks(note_path, full_content, db_path)
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("embed_note_chunks failed for %s: %s",
                           _sanitize_for_log(note_path), exc)


def _note_metadata(note_path: str, fm: Dict, body: str) -> Dict:
    return {
        "path": note_path,
        "title": fm.get("title", Path(note_path).stem),
        "folder": str(Path(note_path).parent) if "/" in note_path else "",
        "tags": fm.get("tags", []),
        "updated_at": fm.get("updated_at", ""),
        "word_count": len(body.split()),
    }
