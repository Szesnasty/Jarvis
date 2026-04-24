from fastapi import APIRouter, HTTPException, Query, UploadFile, File

from models.schemas import JarvisSelfConfigRequest, JarvisSelfConfigResponse
from services import specialist_service

router = APIRouter(prefix="/api/specialists", tags=["specialists"])

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
_UPLOAD_CHUNK = 1024 * 1024  # 1 MB


@router.get("")
async def list_specialists():
    return specialist_service.list_specialists()


@router.get("/active")
async def get_active():
    return specialist_service.get_active_specialists()


# --- JARVIS self-config ---
# Routes for the built-in JARVIS specialist must be declared BEFORE the generic
# `/{spec_id}` routes, otherwise FastAPI's path matcher would route
# `/jarvis/config` into the dynamic spec_id handlers.

@router.get("/jarvis/config", response_model=JarvisSelfConfigResponse)
async def get_jarvis_config():
    """Return only the user-editable JARVIS fields.

    The default Jarvis system prompt is intentionally NOT returned — the user
    sees only their own override (or an empty string). This preserves the
    abstraction that Jarvis has its own private base persona.
    """
    spec = specialist_service.get_jarvis_self()
    if spec is None:
        # Fresh workspace where seed has not run yet — return empty defaults.
        return JarvisSelfConfigResponse()
    return JarvisSelfConfigResponse(
        system_prompt=spec.get("system_prompt", "") or "",
        behavior_extension=spec.get("behavior_extension", "") or "",
    )


@router.put("/jarvis/config", response_model=JarvisSelfConfigResponse)
async def update_jarvis_config(payload: JarvisSelfConfigRequest):
    data = payload.model_dump(exclude_unset=True)
    try:
        spec = specialist_service.update_jarvis_self(data)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="JARVIS specialist not initialised — workspace seed has not run",
        )
    return JarvisSelfConfigResponse(
        system_prompt=spec.get("system_prompt", "") or "",
        behavior_extension=spec.get("behavior_extension", "") or "",
    )


@router.get("/suggest")
async def suggest_specialist(message: str = Query(...)):
    """Suggest a specialist based on the user's message content."""
    suggestion = specialist_service.suggest_specialist(message)
    if suggestion:
        return {"suggested": suggestion}
    return {"suggested": None}


@router.get("/{spec_id}")
async def get_specialist(spec_id: str):
    try:
        return specialist_service.get_specialist(spec_id)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")


@router.post("")
async def create_specialist(data: dict):
    try:
        spec = specialist_service.create_specialist(data)
        return spec
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/{spec_id}")
async def update_specialist(spec_id: str, data: dict):
    try:
        return specialist_service.update_specialist(spec_id, data)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
    except ValueError as exc:
        # Raised when caller tries to edit a protected built-in (e.g. JARVIS).
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/{spec_id}")
async def delete_specialist(spec_id: str):
    try:
        specialist_service.delete_specialist(spec_id)
        return {"status": "deleted"}
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
    except ValueError as exc:
        # JARVIS and other protected built-ins reject deletion.
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/activate/{spec_id}")
async def activate_specialist(spec_id: str):
    try:
        spec = specialist_service.activate_specialist(spec_id)
        is_active = any(s["id"] == spec_id for s in specialist_service.get_active_specialists())
        return {"status": "activated" if is_active else "deactivated", "specialist": spec, "active": specialist_service.get_active_specialists()}
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
    except ValueError as exc:
        # JARVIS rejects toggle — it is implicitly always active.
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/deactivate")
async def deactivate_specialist():
    specialist_service.deactivate_specialist()
    return {"status": "deactivated"}


@router.post("/deactivate/{spec_id}")
async def deactivate_one(spec_id: str):
    specialist_service.deactivate_specialist(spec_id)
    return {"status": "deactivated", "active": specialist_service.get_active_specialists()}


# --- Specialist Files ---


@router.get("/{spec_id}/files")
async def list_files(spec_id: str):
    try:
        return specialist_service.list_specialist_files(spec_id)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")


@router.post("/{spec_id}/files")
async def upload_file(spec_id: str, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=422, detail="Filename is required")
    try:
        # Stream the upload in chunks so oversized payloads are rejected
        # without first buffering the entire file in memory.
        buffers: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(_UPLOAD_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                )
            buffers.append(chunk)
        content = b"".join(buffers)
        return specialist_service.save_specialist_file(spec_id, file.filename, content)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{spec_id}/files/{filename}")
async def delete_file(spec_id: str, filename: str):
    try:
        specialist_service.delete_specialist_file(spec_id, filename)
        return {"status": "deleted"}
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{spec_id}/ingest-url")
async def ingest_specialist_url(spec_id: str, data: dict):
    """Ingest a URL and save as a knowledge file for this specialist."""
    try:
        specialist_service.get_specialist(spec_id)
    except specialist_service.SpecialistNotFoundError:
        raise HTTPException(status_code=404, detail="Specialist not found")

    url = data.get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="Valid URL required")

    from services.url_ingest import ingest_url as _ingest_url, IngestError
    from config import get_settings

    try:
        result = await _ingest_url(url, folder="knowledge", summarize=data.get("summarize", False))

        # Copy the ingested file into the specialist's knowledge dir
        workspace = get_settings().workspace_path
        source_path = workspace / "memory" / result["path"]
        if not source_path.exists():
            raise HTTPException(status_code=500, detail="Ingested file not found")

        return specialist_service.copy_file_to_specialist(
            spec_id, source_path, title=result.get("title", ""),
        )
    except IngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
