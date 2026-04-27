"""Enrichment queue and result endpoints (step 22c)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.enrichment_service import (
    SUBJECT_JIRA,
    SUBJECT_NOTE,
    cancel_queue,
    get_latest_enrichment,
    queue_status,
    rerun,
    sharpen_all,
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


class SharpenAllRequest(BaseModel):
    reason: str = Field(default="manual_sharpen_all", min_length=1, max_length=200)
    include_notes: bool = True
    include_jira: bool = True


@router.post("/sharpen-all", status_code=202)
async def sharpen_all_endpoint(body: SharpenAllRequest | None = None) -> dict:
    """Enqueue every note and Jira issue for local-AI enrichment in one click."""
    payload = body or SharpenAllRequest()
    # Clicking Sharpen is explicit opt-in — enable the worker if it wasn't already.
    from config import get_settings
    from services import preference_service
    preference_service.save_preference("enrichment_enabled", "true",
                                       workspace_path=get_settings().workspace_path)
    return await sharpen_all(
        reason=payload.reason,
        include_notes=payload.include_notes,
        include_jira=payload.include_jira,
    )


@router.delete("/queue", status_code=200)
async def cancel_enrichment_queue() -> dict:
    """Cancel all pending enrichment items and unload the model from memory."""
    # Disable the worker too — without this, any later enqueue (e.g. next
    # Jira import) would immediately resume processing because the user
    # had previously clicked Sharpen. Cancel = "stop AND don't restart".
    from config import get_settings
    from services import preference_service
    preference_service.save_preference("enrichment_enabled", "false",
                                       workspace_path=get_settings().workspace_path)
    removed = await cancel_queue()
    # Unload the enrichment model from Ollama to stop GPU heat immediately
    try:
        from services.enrichment.runtime import select_model_id
        model_id = select_model_id()
        ollama_model = model_id.replace("ollama_chat/", "")
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "http://localhost:11434/api/generate",
                json={"model": ollama_model, "keep_alive": 0},
            )
    except Exception:
        pass  # best-effort; queue is already cleared
    status = await queue_status()
    return {"removed": removed, **status}


@router.get("/{subject_type}/{subject_id:path}")
async def get_enrichment(subject_type: str, subject_id: str) -> dict:
    if subject_type not in {SUBJECT_JIRA, SUBJECT_NOTE}:
        raise HTTPException(status_code=404, detail="Unknown subject_type")

    result = await get_latest_enrichment(subject_type, subject_id)
    if not result:
        raise HTTPException(status_code=404, detail="Enrichment not found")
    return result.get("payload", {})
