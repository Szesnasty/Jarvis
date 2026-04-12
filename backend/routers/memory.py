import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, status

from models.schemas import (
    NoteContentRequest,
    NoteAppendRequest,
    NoteDetailResponse,
    NoteMetadataResponse,
    ReindexResponse,
    UrlIngestRequest,
)
from services.memory_service import (
    NoteExistsError,
    NoteNotFoundError,
    append_note,
    create_note,
    delete_note,
    get_note,
    list_notes,
    reindex_all,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/notes", response_model=List[NoteMetadataResponse])
async def get_notes_list(
    folder: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    results = await list_notes(folder=folder, search=search, limit=limit)
    return results


@router.get("/notes/{note_path:path}", response_model=NoteDetailResponse)
async def get_note_detail(note_path: str):
    try:
        return await get_note(note_path)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")


@router.post("/notes/{note_path:path}", response_model=NoteMetadataResponse, status_code=201)
async def create_note_endpoint(note_path: str, body: NoteContentRequest):
    try:
        return await create_note(note_path, body.content)
    except NoteExistsError:
        raise HTTPException(status_code=409, detail="Note already exists")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/notes/{note_path:path}", response_model=NoteMetadataResponse)
async def append_note_endpoint(note_path: str, body: NoteAppendRequest):
    try:
        return await append_note(note_path, body.append)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/notes/{note_path:path}", status_code=200)
async def delete_note_endpoint(note_path: str):
    try:
        await delete_note(note_path)
        return {"status": "deleted", "path": note_path}
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_endpoint():
    count = await reindex_all()
    return ReindexResponse(indexed=count)


@router.post("/ingest")
async def ingest_file(
    file: UploadFile = File(...),
    folder: str = Form("knowledge"),
):
    from services.ingest import IngestError, fast_ingest

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=Path(file.filename or "upload").suffix,
    ) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await fast_ingest(
            tmp_path,
            target_folder=folder,
            original_name=file.filename,
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    return result


@router.post("/ingest-url")
async def ingest_url_endpoint(body: UrlIngestRequest):
    """Ingest a YouTube video or web article into memory."""
    from services.ingest import IngestError
    from services.url_ingest import ingest_url
    from services.workspace_service import get_api_key

    api_key = get_api_key() if body.summarize else None
    if body.summarize and not api_key:
        raise HTTPException(status_code=400, detail="API key not configured")

    try:
        result = await ingest_url(
            url=body.url,
            folder=body.folder,
            summarize=body.summarize,
            api_key=api_key,
        )
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result


@router.post("/enrich/{note_path:path}")
async def enrich_note(note_path: str):
    """Use AI to auto-generate summary and tags for a note."""
    from services.ingest import IngestError, smart_enrich
    from services.workspace_service import get_api_key

    api_key = get_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key not configured")

    try:
        result = await smart_enrich(note_path, api_key)
    except IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result
