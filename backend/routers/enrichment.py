"""Enrichment queue and result endpoints (step 22c)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.enrichment_service import (
    SUBJECT_JIRA,
    SUBJECT_NOTE,
    get_latest_enrichment,
    queue_status,
    rerun,
)

router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


class RerunRequest(BaseModel):
    subject_type: Optional[str] = None
    subject_ids: Optional[list[str]] = None
    reason: str = Field(min_length=1, max_length=200)


@router.get("/queue")
async def get_queue() -> dict:
    return await queue_status()


@router.post("/rerun", status_code=202)
async def rerun_enrichment(body: RerunRequest) -> dict:
    if body.subject_type and body.subject_type not in {SUBJECT_JIRA, SUBJECT_NOTE}:
        raise HTTPException(status_code=422, detail="Unsupported subject_type")

    queued = await rerun(
        reason=body.reason,
        subject_type=body.subject_type,
        subject_ids=body.subject_ids,
    )
    return {"queued": queued}


@router.get("/{subject_type}/{subject_id:path}")
async def get_enrichment(subject_type: str, subject_id: str) -> dict:
    if subject_type not in {SUBJECT_JIRA, SUBJECT_NOTE}:
        raise HTTPException(status_code=404, detail="Unknown subject_type")

    result = await get_latest_enrichment(subject_type, subject_id)
    if not result:
        raise HTTPException(status_code=404, detail="Enrichment not found")
    return result.get("payload", {})
