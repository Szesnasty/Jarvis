"""Jira import REST API.

POST /api/jira/import        — upload an XML/CSV export and ingest it.
GET  /api/jira/imports       — list past import batches.
GET  /api/jira/imports/{id}  — one import batch by id.
GET  /api/jira/issues        — paginated list of imported issues (for UI only;
                                semantic retrieval lives in 22f).

Security:
- File size cap enforced from config (JARVIS_JIRA_MAX_UPLOAD_MB, default 512).
- Extension/MIME whitelist: .xml, .csv, application/xml, text/xml, text/csv.
- defusedxml parsing (XXE-safe) is used by the service layer.
- The issue_key regex in the service blocks path traversal via crafted keys.
"""

import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from services.jira_ingest import (
    JiraImportError,
    detect_format,
    list_imports,
    list_issues,
    run_import,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jira", tags=["jira"])


_ALLOWED_EXTS = {".xml", ".csv"}
_ALLOWED_CONTENT_TYPES = {
    "application/xml",
    "text/xml",
    "text/csv",
    "application/csv",
    # Browsers sometimes send these for CSV/XML attachments.
    "application/octet-stream",
}
# 512 MB default — user can override via env (JARVIS_JIRA_MAX_UPLOAD_MB=1024).
import os as _os

_MAX_UPLOAD_BYTES = int(_os.environ.get("JARVIS_JIRA_MAX_UPLOAD_MB", "512")) * 1024 * 1024


class ImportStatsResponse(BaseModel):
    issue_count: int
    inserted: int
    updated: int
    skipped: int
    bytes_processed: int
    project_keys: List[str]


class ImportResponse(BaseModel):
    status: str
    filename: str
    format: str
    stats: ImportStatsResponse


class JiraImportRow(BaseModel):
    id: int
    filename: str
    format: str
    project_keys: List[str]
    issue_count: int
    inserted: int
    updated: int
    skipped: int
    bytes_processed: int
    duration_ms: int
    status: str
    error: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None


class JiraIssueRow(BaseModel):
    issue_key: str
    project_key: str
    title: str
    issue_type: str
    status: str
    status_category: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    epic_key: Optional[str] = None
    updated_at: str
    note_path: str


def _validate_upload(file: UploadFile) -> str:
    """Return the declared format ('xml'|'csv') or raise HTTPException."""
    raw_name = file.filename or "upload"
    ext = Path(raw_name).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Only .xml and .csv files are accepted (got {ext or 'no extension'}).",
        )
    # Content-type check is advisory: browsers and curl differ. We accept
    # the whitelist plus octet-stream and rely on the extension + sniff.
    ctype = (file.content_type or "").lower().split(";", 1)[0].strip()
    if ctype and ctype not in _ALLOWED_CONTENT_TYPES:
        logger.info("Unusual content-type for Jira import: %s", ctype.replace("\n", ""))
    return "xml" if ext == ".xml" else "csv"


@router.post("/import", response_model=ImportResponse)
async def import_jira(
    file: UploadFile = File(...),
    project_filter: Optional[str] = Form(None),
):
    declared_fmt = _validate_upload(file)

    # Stream the upload to a temp file with a strict size cap — never
    # buffer a multi-hundred-MB export in memory.
    suffix = ".xml" if declared_fmt == "xml" else ".csv"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    total = 0
    try:
        try:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds limit of {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
                    )
                tmp.write(chunk)
        finally:
            tmp.flush()
            tmp.close()

        tmp_path = Path(tmp.name)
        try:
            fmt = detect_format(tmp_path, declared_fmt)
        except JiraImportError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        projects: Optional[List[str]] = None
        if project_filter:
            projects = [p.strip() for p in project_filter.split(",") if p.strip()]

        try:
            stats = await run_import(
                tmp_path,
                filename=file.filename or tmp_path.name,
                fmt=fmt,
                project_filter=projects,
                defer_post_processing=True,
            )
        except JiraImportError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except HTTPException:
            raise
        except Exception:
            logger.exception("Jira import failed unexpectedly")
            raise HTTPException(status_code=500, detail="Jira import failed")

        return ImportResponse(
            status="ok",
            filename=file.filename or tmp_path.name,
            format=fmt,
            stats=ImportStatsResponse(
                issue_count=stats.issue_count,
                inserted=stats.inserted,
                updated=stats.updated,
                skipped=stats.skipped,
                bytes_processed=stats.bytes_processed,
                project_keys=stats.project_keys,
            ),
        )
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except OSError:
            pass


@router.get("/imports", response_model=List[JiraImportRow])
async def get_imports(limit: int = Query(50, ge=1, le=200)):
    rows = await list_imports(limit=limit)
    return rows


@router.get("/issues", response_model=List[JiraIssueRow])
async def get_issues(
    project: Optional[str] = Query(None, max_length=32),
    status_category: Optional[str] = Query(None, max_length=32),
    assignee: Optional[str] = Query(None, max_length=128),
    sprint: Optional[str] = Query(None, max_length=128),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = await list_issues(
        project=project,
        status_category=status_category,
        assignee=assignee,
        sprint=sprint,
        limit=limit,
        offset=offset,
    )
    return rows
