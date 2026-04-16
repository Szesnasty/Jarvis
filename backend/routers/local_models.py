"""Local models router — hardware probe, runtime status, model catalog & pull."""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from services.ollama_service import (
    HardwareProfile,
    ModelRecommendation,
    PullRequest,
    RuntimeStatus,
    SelectRequest,
    TestRequest,
    TestResponse,
    WarmUpRequest,
    build_catalog,
    delete_model,
    get_active_local_model,
    list_installed_models,
    probe_hardware,
    probe_runtime,
    pull_model_stream,
    set_active_local_model,
    test_model,
    warm_up_model,
    DEFAULT_OLLAMA_BASE_URL,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/local", tags=["local-models"])


@router.get("/hardware", response_model=HardwareProfile)
async def get_hardware() -> HardwareProfile:
    """Detect local hardware profile (RAM, disk, CPU, GPU)."""
    return probe_hardware()


@router.get("/runtime", response_model=RuntimeStatus)
async def get_runtime(
    base_url: str = Query(DEFAULT_OLLAMA_BASE_URL, alias="base_url"),
) -> RuntimeStatus:
    """Check if Ollama is installed and running."""
    return await probe_runtime(base_url)


@router.get("/models/catalog")
async def get_catalog(
    base_url: str = Query(DEFAULT_OLLAMA_BASE_URL, alias="base_url"),
) -> list:
    """Return model catalog with hardware-based recommendations."""
    hw = probe_hardware()
    active = get_active_local_model()
    active_id = active.get("model_id") if active else None
    catalog = await build_catalog(hw, base_url, active_model_id=active_id)
    return [r.model_dump() for r in catalog]


@router.get("/models/installed")
async def get_installed(
    base_url: str = Query(DEFAULT_OLLAMA_BASE_URL, alias="base_url"),
) -> list:
    """List models currently downloaded in Ollama."""
    return await list_installed_models(base_url)


@router.post("/models/pull")
async def pull_model(req: PullRequest):
    """Pull (download) a model from Ollama. Streams progress via SSE."""
    return StreamingResponse(
        pull_model_stream(req.model, req.base_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/models/select")
async def select_model(req: SelectRequest):
    """Set the active local model."""
    set_active_local_model(req.model_id, req.litellm_model, req.base_url)
    return {"status": "ok", "active_model": req.model_id}


@router.delete("/models/{model_name:path}")
async def remove_model(
    model_name: str,
    base_url: str = Query(DEFAULT_OLLAMA_BASE_URL, alias="base_url"),
):
    """Delete a model from Ollama."""
    success = await delete_model(model_name, base_url)
    if success:
        return {"status": "ok", "deleted": model_name}
    return {"status": "error", "message": "Failed to delete model"}


@router.post("/models/test", response_model=TestResponse)
async def test_model_endpoint(req: TestRequest) -> TestResponse:
    """Quick test that a model works — returns latency and speed."""
    return await test_model(req.model, req.base_url)


@router.post("/models/warm-up")
async def warm_up(req: WarmUpRequest):
    """Send a tiny prompt to keep model loaded in Ollama memory."""
    success = await warm_up_model(req.model, req.base_url)
    return {"status": "warm" if success else "failed"}
