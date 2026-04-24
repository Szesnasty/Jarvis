"""Connections API — Smart Connect (Step 25 PR 4).

Initial surface: semantic-orphan listing and explicit re-run of
``connect_note``. Promote/dismiss endpoints are deferred to a later PR
(they need a ``dismissed_suggestions`` table).
"""

from __future__ import annotations

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
