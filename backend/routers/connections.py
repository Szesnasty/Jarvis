"""Connections API — Smart Connect (Step 25 PR 4 + PR 5).

Endpoints:
  * ``GET  /orphans``               — list semantic-orphan notes
  * ``POST /run/{path}``            — re-run Smart Connect for a note
  * ``POST /dismiss``               — dismiss a suggestion pair
  * ``POST /promote``               — promote a suggestion to ``related``
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.connection_service import ConnectionResult, connect_note

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
