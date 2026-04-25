import re
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


@router.post("/reindex-embeddings")
async def reindex_embeddings_endpoint():
    """Rebuild all note embeddings from markdown files."""
    try:
        from services.embedding_service import reindex_all as reindex_embeddings_all
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable (fastembed not installed)",
        )
    try:
        count = await reindex_embeddings_all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}")
    return {"status": "ok", "notes_embedded": count}


@router.get("/semantic-search")
async def semantic_search_endpoint(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    """Standalone semantic search using embeddings only."""
    try:
        from services.embedding_service import is_available, search_similar
    except ImportError:
        return {"results": [], "mode": "unavailable", "error": "fastembed not installed"}

    if not is_available():
        return {"results": [], "mode": "unavailable", "error": "fastembed not installed"}

    try:
        results = await search_similar(q, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Semantic search failed: {exc}")

    return {
        "results": [
            {"path": path, "similarity": round(score, 3)}
            for path, score in results
        ],
        "mode": "semantic",
    }


MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB (supports large Jira CSV/XML exports)
_UPLOAD_CHUNK = 1024 * 1024  # 1 MB chunks when streaming uploads to disk
_FOLDER_RE = re.compile(r"^[a-zA-Z0-9-]+$")


@router.post("/ingest")
async def ingest_file(
    file: UploadFile = File(...),
    folder: str = Form("knowledge"),
):
    from services.ingest import IngestError, fast_ingest
    from services import ingest_jobs

    # Validate folder against path traversal
    if not _FOLDER_RE.match(folder):
        raise HTTPException(status_code=400, detail="Invalid folder name")

    job_id = ingest_jobs.start_job(file.filename or "upload", kind="file")
    error_for_job: Optional[str] = None
    try:
        # Stream the upload to a temp file in chunks so we never hold the
        # full payload in memory (large Jira exports can be hundreds of MB).
        ingest_jobs.update_stage(job_id, "uploading")
        written = 0
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(file.filename or "upload").suffix,
        ) as tmp:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    tmp.close()
                    Path(tmp.name).unlink(missing_ok=True)
                    error_for_job = f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
                    raise HTTPException(status_code=413, detail=error_for_job)
                tmp.write(chunk)
            tmp_path = Path(tmp.name)

        try:
            result = await fast_ingest(
                tmp_path,
                target_folder=folder,
                original_name=file.filename,
                job_id=job_id,
            )
        except IngestError as exc:
            error_for_job = str(exc)
            raise HTTPException(status_code=400, detail=error_for_job)
        finally:
            tmp_path.unlink(missing_ok=True)

        return result
    finally:
        ingest_jobs.finish_job(job_id, error=error_for_job)


@router.get("/ingest/status")
async def ingest_status():
    """Snapshot of currently running and recently finished ingest jobs."""
    from services import ingest_jobs
    return ingest_jobs.snapshot()


@router.post("/ingest-url")
async def ingest_url_endpoint(body: UrlIngestRequest):
    """Ingest a YouTube video or web article into memory."""
    from services.ingest import IngestError
    from services.url_ingest import ingest_url
    from services.workspace_service import get_api_key
    from services import ingest_jobs

    api_key = get_api_key() if body.summarize else None
    if body.summarize and not api_key:
        raise HTTPException(status_code=400, detail="API key not configured")

    kind = "youtube" if "youtube.com" in body.url or "youtu.be" in body.url else "url"
    job_id = ingest_jobs.start_job(body.url, kind=kind)
    error_for_job: Optional[str] = None
    try:
        try:
            result = await ingest_url(
                url=body.url,
                folder=body.folder,
                summarize=body.summarize,
                api_key=api_key,
            )
        except IngestError as exc:
            error_for_job = str(exc)
            raise HTTPException(status_code=400, detail=error_for_job)

        return result
    finally:
        ingest_jobs.finish_job(job_id, error=error_for_job)


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
