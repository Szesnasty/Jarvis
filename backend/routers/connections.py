"""Connections API — Smart Connect (Step 25 PR 4 + PR 5, Step 26a).

Endpoints:
  * ``GET  /orphans``               — list semantic-orphan notes
  * ``POST /run/{path}``            — re-run Smart Connect for a note
  * ``POST /dismiss``               — dismiss a suggestion pair
  * ``POST /promote``               — promote a suggestion to ``related``
  * ``POST /backfill``              — run Smart Connect on all (or orphan) notes (SSE)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.schemas import BackfillRequest
from services.connection_service import ConnectionResult, connect_note

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connections", tags=["connections"])


class OrphanItem(BaseModel):
    id: str
    label: str
    folder: str = ""


@router.get("/orphans", response_model=List[OrphanItem])
async def list_semantic_orphans() -> List[OrphanItem]:
    """List notes with no semantically meaningful neighbours."""
    from services.graph_service import find_semantic_orphans

    return [OrphanItem(**o) for o in find_semantic_orphans()]


@router.post("/run/{note_path:path}", response_model=ConnectionResult)
async def rerun_connect(
    note_path: str,
    mode: Optional[str] = "fast",
) -> ConnectionResult:
    """Re-run Smart Connect for an existing note. ``mode`` is ``fast`` or ``aggressive``."""
    if mode not in ("fast", "aggressive"):
        raise HTTPException(status_code=400, detail="mode must be 'fast' or 'aggressive'")
    try:
        return await connect_note(note_path, mode=mode)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class SuggestionPair(BaseModel):
    note_path: str
    target_path: str


class DismissResponse(BaseModel):
    note_path: str
    target_path: str
    dismissed: bool


class PromoteResponse(BaseModel):
    note_path: str
    target_path: str
    related: List[str]


def _workspace() -> Path:
    from config import get_settings
    return get_settings().workspace_path


@router.post("/dismiss", response_model=DismissResponse)
async def dismiss_suggestion(payload: SuggestionPair) -> DismissResponse:
    """Persist a user dismissal so the pair never reappears as a suggestion."""
    from services.dismissed_suggestions import dismiss
    from services.memory_service import _db_path, _validate_path

    ws = _workspace()
    mem = ws / "memory"
    _validate_path(payload.note_path, mem)
    _validate_path(payload.target_path, mem)
    dismiss(_db_path(ws), payload.note_path, payload.target_path)
    return DismissResponse(
        note_path=payload.note_path,
        target_path=payload.target_path,
        dismissed=True,
    )


@router.post("/promote", response_model=PromoteResponse)
async def promote_suggestion(payload: SuggestionPair) -> PromoteResponse:
    """Promote a suggested link into the note's ``related`` list."""
    from services.memory_service import _validate_path
    from utils.markdown import add_frontmatter, parse_frontmatter

    ws = _workspace()
    mem = ws / "memory"
    _validate_path(payload.note_path, mem)
    _validate_path(payload.target_path, mem)

    full_path = mem / payload.note_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Note not found: {payload.note_path}")

    fm, body = parse_frontmatter(full_path.read_text(encoding="utf-8"))
    related = list(fm.get("related") or [])
    if payload.target_path not in related:
        related.append(payload.target_path)
    fm["related"] = related

    # Drop the promoted target from suggested_related to avoid duplication.
    suggested = fm.get("suggested_related") or []
    fm["suggested_related"] = [
        s for s in suggested
        if not (isinstance(s, dict) and s.get("path") == payload.target_path)
    ]
    full_path.write_text(add_frontmatter(body, fm), encoding="utf-8")

    return PromoteResponse(
        note_path=payload.note_path,
        target_path=payload.target_path,
        related=related,
    )


@router.post("/backfill")
async def backfill_connections(payload: BackfillRequest) -> StreamingResponse:
    """Run Smart Connect on all (or orphan-only) notes, streaming JSON progress.

    Returns ``Content-Type: text/event-stream``. The frontend MUST consume
    this via ``fetch()`` + ``ReadableStream`` — NOT via native ``EventSource``
    (which only supports GET). Each emitted line is a JSON-encoded
    ``BackfillProgress`` object.
    """
    ws = _workspace()

    async def _stream() -> AsyncGenerator[str, None]:
        import aiosqlite

        from services.connection_service import (
            CURRENT_SMART_CONNECT_VERSION,
            connect_note as _connect,
        )
        from services.graph_service import find_semantic_orphans, is_semantic_orphan
        from services.memory_service import _db_path
        from utils.markdown import parse_frontmatter

        db_p = _db_path(ws)

        # ── Collect note paths ────────────────────────────────────────────
        try:
            if payload.only_orphans:
                orphan_nodes = find_semantic_orphans(workspace_path=ws)
                paths = [
                    o["id"][len("note:"):]
                    for o in orphan_nodes
                    if o["id"].startswith("note:")
                ]
            else:
                async with aiosqlite.connect(str(db_p)) as db:
                    cursor = await db.execute("SELECT path FROM notes ORDER BY path")
                    rows = await cursor.fetchall()
                    paths = [row[0] for row in rows]
        except Exception as exc:
            logger.warning("backfill path collection failed: %s", exc)
            yield json.dumps({
                "done": 0, "total": 0, "suggestions_added": 0,
                "notes_changed": 0, "skipped": 0, "orphans_found": 0,
                "dry_run": payload.dry_run, "error": str(exc),
            }) + "\n"
            return

        total = len(paths)
        done = 0
        suggestions_added = 0
        notes_changed = 0
        skipped_count = 0
        orphans_found = 0

        for batch_start in range(0, max(total, 1), payload.batch_size):
            batch = paths[batch_start: batch_start + payload.batch_size]

            for note_path in batch:
                full_path = ws / "memory" / note_path
                if not full_path.exists():
                    done += 1
                    continue

                # ── Per-note skip logic ───────────────────────────────────
                if not payload.force:
                    try:
                        raw = full_path.read_text(encoding="utf-8")
                        fm, _ = parse_frontmatter(raw)
                        sc = fm.get("smart_connect")
                        version = sc.get("version", 0) if isinstance(sc, dict) else 0
                        has_suggestions = "suggested_related" in fm

                        if version >= CURRENT_SMART_CONNECT_VERSION and has_suggestions:
                            try:
                                orphan = is_semantic_orphan(note_path, workspace_path=ws)
                            except Exception:
                                orphan = False

                            if not orphan:
                                skipped_count += 1
                                done += 1
                                continue
                            else:
                                orphans_found += 1
                    except Exception:
                        pass  # Unreadable note — fall through and process it

                # ── Run Smart Connect ─────────────────────────────────────
                try:
                    result = await _connect(
                        note_path,
                        workspace_path=ws,
                        mode=payload.mode,
                        dry_run=payload.dry_run,
                        min_confidence=payload.min_confidence,
                    )
                    added = len(result.suggested)
                    suggestions_added += added
                    if added > 0:
                        notes_changed += 1
                except Exception as exc:
                    logger.warning("backfill failed for %s: %s", note_path, exc)

                done += 1

            # ── Emit batch progress ───────────────────────────────────────
            yield json.dumps({
                "done": done,
                "total": total,
                "suggestions_added": suggestions_added,
                "notes_changed": notes_changed,
                "skipped": skipped_count,
                "orphans_found": orphans_found,
                "dry_run": payload.dry_run,
            }) + "\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")
