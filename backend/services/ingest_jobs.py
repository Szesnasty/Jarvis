"""In-memory ingest job tracker.

Tracks active file/URL ingest operations so the UI can display a global
status badge ("Ingesting 3/6 files…") next to the ALIVE indicator while
the user navigates the app.

This is intentionally process-local and ephemeral. Background workers and
ingest endpoints call ``start_job`` when work begins and ``finish_job``
when it ends (success or failure). The frontend polls
``GET /api/memory/ingest/status`` every few seconds.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class IngestJob:
    id: str
    name: str
    kind: str  # "file" | "url" | "youtube" | "graph_rebuild"
    started_at: float
    size_bytes: Optional[int] = None
    status: str = "running"  # "running" | "done" | "failed"
    stage: str = "processing"  # "uploading" | "extracting" | "indexing" | "embedding" | "linking" | "done"
    error: Optional[str] = None
    finished_at: Optional[float] = None


_lock = threading.Lock()
_jobs: Dict[str, IngestJob] = {}
# Recently finished jobs are kept briefly so the UI can show "✓ done" before fading.
_FINISHED_TTL_S = 8.0

# Separate flag for the background graph rebuild so we only run one at a time
# and can report its progress as a dedicated job in the status snapshot.
_rebuild_job_id: Optional[str] = None


def schedule_graph_rebuild(workspace_path=None) -> None:
    """Fire a background rebuild_graph() if none is already running.

    Called automatically after each file ingest.  The rebuild is tracked as a
    special ``kind="graph_rebuild"`` job so the frontend can show a
    "Building graph…" indicator without blocking the ingest response.
    """
    global _rebuild_job_id
    with _lock:
        # Skip if a rebuild job is already running.
        if _rebuild_job_id is not None:
            existing = _jobs.get(_rebuild_job_id)
            if existing is not None and existing.status == "running":
                return

    job_id = start_job("Graph rebuild", kind="graph_rebuild")
    with _lock:
        _rebuild_job_id = job_id

    def _run():
        import logging
        log = logging.getLogger(__name__)
        try:
            update_stage(job_id, "rebuilding")
            from services.graph_service import rebuild_graph
            rebuild_graph(workspace_path=workspace_path)
            finish_job(job_id)
        except Exception as exc:
            log.warning("Background graph rebuild failed: %s", exc)
            finish_job(job_id, error=str(exc))

    t = threading.Thread(target=_run, daemon=True, name="graph-rebuild")
    t.start()


def _prune_finished_locked() -> None:
    now = time.time()
    expired = [
        jid for jid, job in _jobs.items()
        if job.finished_at is not None and (now - job.finished_at) > _FINISHED_TTL_S
    ]
    for jid in expired:
        _jobs.pop(jid, None)


def start_job(name: str, *, kind: str = "file", size_bytes: Optional[int] = None) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _prune_finished_locked()
        _jobs[job_id] = IngestJob(
            id=job_id,
            name=name,
            kind=kind,
            started_at=time.time(),
            size_bytes=size_bytes,
        )
    return job_id


def finish_job(job_id: str, *, error: Optional[str] = None) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.status = "failed" if error else "done"
        job.stage = "failed" if error else "done"
        job.error = error
        job.finished_at = time.time()
        _prune_finished_locked()


def update_stage(job_id: str, stage: str) -> None:
    """Mark which step the job is currently on (extracting / indexing / ...)."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.stage = stage


def snapshot() -> dict:
    """Return a JSON-serialisable snapshot of current ingest state."""
    with _lock:
        _prune_finished_locked()
        running: List[dict] = []
        recently_done: List[dict] = []
        for job in _jobs.values():
            payload = {
                "id": job.id,
                "name": job.name,
                "kind": job.kind,
                "size_bytes": job.size_bytes,
                "status": job.status,
                "stage": job.stage,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "error": job.error,
            }
            if job.status == "running":
                running.append(payload)
            else:
                recently_done.append(payload)
        return {
            "active_count": len(running),
            "active": running,
            "recent": recently_done,
        }
