"""Connections API — Smart Connect (Step 25 PR 4 + PR 5, Step 26a, Step 26c).

Endpoints:
  * ``GET  /orphans``               — list semantic-orphan notes
  * ``POST /run/{path}``            — re-run Smart Connect for a note
  * ``POST /dismiss``               — dismiss a suggestion pair
  * ``POST /promote``               — promote a suggestion to ``related``
  * ``POST /backfill``              — run Smart Connect on all (or orphan) notes (SSE)
  * ``GET  /stats``                 — workspace-level quality metrics
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
    from services.connection_events import write_event
    from services.dismissed_suggestions import dismiss
    from services.memory_service import _db_path, _validate_path

    ws = _workspace()
    mem = ws / "memory"
    _validate_path(payload.note_path, mem)
    _validate_path(payload.target_path, mem)
    db_p = _db_path(ws)
    dismiss(db_p, payload.note_path, payload.target_path)

    # Extract confidence/methods/tier from current frontmatter for analytics.
    confidence, methods, tier = _extract_suggestion_meta(
        ws, payload.note_path, payload.target_path
    )
    from services.connection_service import CURRENT_SMART_CONNECT_VERSION
    write_event(
        db_p,
        event_type="dismiss",
        note_path=payload.note_path,
        target_path=payload.target_path,
        confidence=confidence,
        methods=methods,
        tier=tier,
        smart_connect_version=CURRENT_SMART_CONNECT_VERSION,
    )

    return DismissResponse(
        note_path=payload.note_path,
        target_path=payload.target_path,
        dismissed=True,
    )


@router.post("/promote", response_model=PromoteResponse)
async def promote_suggestion(payload: SuggestionPair) -> PromoteResponse:
    """Promote a suggested link into the note's ``related`` list."""
    from services.connection_events import write_event
    from services.memory_service import _db_path, _validate_path
    from utils.markdown import add_frontmatter, parse_frontmatter

    ws = _workspace()
    mem = ws / "memory"
    _validate_path(payload.note_path, mem)
    _validate_path(payload.target_path, mem)

    full_path = mem / payload.note_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Note not found: {payload.note_path}")

    fm, body = parse_frontmatter(full_path.read_text(encoding="utf-8"))

    # Extract meta BEFORE removing from suggested_related.
    confidence, methods, tier = _suggestion_meta_from_fm(fm, payload.target_path)

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

    from services.connection_service import CURRENT_SMART_CONNECT_VERSION
    write_event(
        _db_path(ws),
        event_type="promote",
        note_path=payload.note_path,
        target_path=payload.target_path,
        confidence=confidence,
        methods=methods,
        tier=tier,
        smart_connect_version=CURRENT_SMART_CONNECT_VERSION,
    )

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
                    await db.execute("PRAGMA busy_timeout = 5000")
                    cursor = await db.execute("SELECT path FROM notes ORDER BY path")
                    rows = await cursor.fetchall()
                    paths = [row[0] for row in rows]
        except Exception:
            # Log full traceback locally, but only return a generic message to the
            # client — exception text may include filesystem paths or query
            # fragments and the SSE stream is exposed to the browser (CodeQL).
            logger.exception("backfill path collection failed")
            yield json.dumps({
                "done": 0, "total": 0, "suggestions_added": 0,
                "notes_changed": 0, "skipped": 0, "orphans_found": 0,
                "dry_run": payload.dry_run,
                "error": "Internal error during path collection.",
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

                    # Write backfill_suggested events (skip in dry_run, dedup per day).
                    if not payload.dry_run and result.suggested:
                        from services.connection_events import (
                            backfill_suggested_dedup_key_exists,
                            write_event,
                        )
                        from services.connection_service import CURRENT_SMART_CONNECT_VERSION

                        today = _now_date()
                        for s in result.suggested:
                            if not backfill_suggested_dedup_key_exists(
                                db_p,
                                note_path=note_path,
                                target_path=s.path,
                                smart_connect_version=CURRENT_SMART_CONNECT_VERSION,
                                today=today,
                            ):
                                write_event(
                                    db_p,
                                    event_type="backfill_suggested",
                                    note_path=note_path,
                                    target_path=s.path,
                                    confidence=s.confidence,
                                    methods=s.methods,
                                    tier=s.tier,
                                    smart_connect_version=CURRENT_SMART_CONNECT_VERSION,
                                )
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


# ---------------------------------------------------------------------------
# Helpers for event metadata extraction
# ---------------------------------------------------------------------------

def _now_date() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _suggestion_meta_from_fm(
    fm: dict,
    target_path: str,
) -> tuple:
    """Extract (confidence, methods, tier) for target_path from a note's frontmatter."""
    for s in fm.get("suggested_related") or []:
        if isinstance(s, dict) and s.get("path") == target_path:
            return (
                s.get("confidence"),
                s.get("methods"),
                s.get("tier"),
            )
    return (None, None, None)


def _extract_suggestion_meta(ws: Path, note_path: str, target_path: str) -> tuple:
    """Read frontmatter from note and return (confidence, methods, tier) for target."""
    try:
        from utils.markdown import parse_frontmatter
        full_path = ws / "memory" / note_path
        if not full_path.exists():
            return (None, None, None)
        fm, _ = parse_frontmatter(full_path.read_text(encoding="utf-8"))
        return _suggestion_meta_from_fm(fm, target_path)
    except Exception:
        return (None, None, None)


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

@router.get("/stats")
async def connection_stats() -> dict:
    """Workspace-level Smart Connect quality metrics.

    ``method_breakdown`` comes from frontmatter ``suggested_related[].methods``
    (not from alias_index) — this counts actual signals that drove suggestions.
    ``events.*`` comes from the ``connection_events`` analytics table.
    ``alias_index.*`` is index health only and is not mixed with method stats.
    """
    import aiosqlite
    import sqlite3

    from services.graph_service import find_semantic_orphans
    from services.memory_service import _db_path

    ws = _workspace()
    db_p = _db_path(ws)
    mem = ws / "memory"

    # ── Note counts ───────────────────────────────────────────────────────
    notes_total = 0
    notes_with_suggestions = 0
    notes_with_related = 0
    method_counts: dict = {}
    orphan_ids: set = set()
    orphan_with_suggestions: set = set()

    try:
        for orphan in find_semantic_orphans(workspace_path=ws):
            orphan_ids.add(orphan["id"])
    except Exception:
        pass

    if mem.exists():
        try:
            for note_path in _iter_note_paths(db_p, mem):
                full_path = mem / note_path
                if not full_path.exists():
                    continue
                notes_total += 1
                try:
                    from utils.markdown import parse_frontmatter
                    fm, _ = parse_frontmatter(full_path.read_text(encoding="utf-8"))
                    suggestions = fm.get("suggested_related") or []
                    if suggestions:
                        notes_with_suggestions += 1
                        node_id = f"note:{note_path}"
                        if node_id in orphan_ids:
                            orphan_with_suggestions.add(node_id)
                        for s in suggestions:
                            if isinstance(s, dict):
                                for m in s.get("methods") or []:
                                    method_counts[m] = method_counts.get(m, 0) + 1
                    if fm.get("related"):
                        notes_with_related += 1
                except Exception:
                    pass
        except Exception:
            pass

    semantic_orphans_total = len(orphan_ids)
    semantic_orphans_with_suggestions = len(orphan_with_suggestions)
    semantic_orphans_without_suggestions = semantic_orphans_total - semantic_orphans_with_suggestions

    # ── Suggestions total ─────────────────────────────────────────────────
    suggestions_total = sum(method_counts.values())

    # ── Event aggregations ────────────────────────────────────────────────
    events: dict = {
        "promoted_total": 0,
        "dismissed_total": 0,
        "acceptance_rate": None,
        "promoted_by_method": {},
        "dismissed_by_method": {},
    }
    alias_index: dict = {
        "phrases_total": 0,
        "weak_phrases_total": 0,
        "blocked_phrases_total": 0,
    }

    if db_p.exists():
        try:
            with sqlite3.connect(str(db_p)) as conn:
                # Event counts
                ev_rows = conn.execute(
                    "SELECT event_type, COUNT(*) FROM connection_events"
                    " WHERE event_type IN ('promote', 'dismiss')"
                    " GROUP BY event_type"
                ).fetchall()
                for ev_type, count in ev_rows:
                    if ev_type == "promote":
                        events["promoted_total"] = count
                    elif ev_type == "dismiss":
                        events["dismissed_total"] = count

                total_decisions = events["promoted_total"] + events["dismissed_total"]
                if total_decisions > 0:
                    events["acceptance_rate"] = round(
                        events["promoted_total"] / total_decisions, 3
                    )

                # promoted_by_method
                promo_rows = conn.execute(
                    "SELECT methods_json FROM connection_events WHERE event_type = 'promote'"
                ).fetchall()
                for (mj,) in promo_rows:
                    if mj:
                        try:
                            import json as _json
                            for m in _json.loads(mj):
                                events["promoted_by_method"][m] = events["promoted_by_method"].get(m, 0) + 1
                        except Exception:
                            pass

                # dismissed_by_method
                dism_rows = conn.execute(
                    "SELECT methods_json FROM connection_events WHERE event_type = 'dismiss'"
                ).fetchall()
                for (mj,) in dism_rows:
                    if mj:
                        try:
                            import json as _json
                            for m in _json.loads(mj):
                                events["dismissed_by_method"][m] = events["dismissed_by_method"].get(m, 0) + 1
                        except Exception:
                            pass

                # alias index health
                try:
                    phrases_total = conn.execute(
                        "SELECT COUNT(DISTINCT phrase_norm) FROM alias_index"
                    ).fetchone()[0]
                    weak_phrases_total = conn.execute(
                        "SELECT COUNT(DISTINCT phrase_norm) FROM alias_index WHERE kind = 'weak_alias'"
                    ).fetchone()[0]
                    alias_index["phrases_total"] = phrases_total
                    alias_index["weak_phrases_total"] = weak_phrases_total
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "notes_total": notes_total,
        "notes_with_suggestions": notes_with_suggestions,
        "notes_with_related": notes_with_related,
        "semantic_orphans_total": semantic_orphans_total,
        "semantic_orphans_with_suggestions": semantic_orphans_with_suggestions,
        "semantic_orphans_without_suggestions": semantic_orphans_without_suggestions,
        "suggestions_total": suggestions_total,
        "method_breakdown": method_counts,
        "events": events,
        "alias_index": alias_index,
    }


def _iter_note_paths(db_p: Path, mem: Path):
    """Yield note paths from DB if available, else walk the memory directory."""
    import sqlite3

    if db_p.exists():
        try:
            with sqlite3.connect(str(db_p)) as conn:
                rows = conn.execute("SELECT path FROM notes ORDER BY path").fetchall()
            if rows:
                for (p,) in rows:
                    yield p
                return
        except Exception:
            pass
    # Fallback: walk filesystem
    for f in sorted(mem.rglob("*.md")):
        yield str(f.relative_to(mem))
