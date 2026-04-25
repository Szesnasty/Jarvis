"""Step 28b plan B — idempotent _finalise + coverage endpoint + auto-queue.

Verifies the three architectural fixes for split-document UX gaps:

* ``_finalise`` does not rewrite a note's frontmatter when the new
  suggestions are byte-equivalent to the existing ones (eliminates
  Obsidian/git noise from "Run on all notes").
* ``GET /api/connections/coverage`` reports section-level pending counts
  the UI uses to drive the SmartConnectStatus badge.
* ``schedule_section_connect`` returns a tracked ingest_jobs id so the
  UI can show "Connecting N sections…" while it runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.connection_service import (
    CURRENT_SMART_CONNECT_VERSION,
    SuggestedLink,
    _finalise,
    _suggestions_fingerprint,
    schedule_section_connect,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
async def ws_db(tmp_path: Path):
    (tmp_path / "memory" / "knowledge").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    await init_database(tmp_path / "app" / "jarvis.db")
    return tmp_path


# ── Fingerprint helper ────────────────────────────────────────────


def test_fingerprint_ignores_volatile_fields():
    a = [
        SuggestedLink(
            path="a.md", confidence=0.815, methods=["bm25", "note_emb"],
            suggested_at="2026-01-01T00:00:00Z",
            score_breakdown={"bm25": 0.5, "note_emb": 0.3},
        ),
    ]
    b = [
        SuggestedLink(
            path="a.md", confidence=0.8154, methods=["note_emb", "bm25"],
            suggested_at="2026-04-25T12:34:56Z",
            score_breakdown={"bm25": 0.55, "note_emb": 0.27},
        ),
    ]
    # Same path, same rounded confidence, same method set → same fingerprint.
    assert _suggestions_fingerprint(a) == _suggestions_fingerprint(b)


def test_fingerprint_detects_methods_change():
    a = [SuggestedLink(path="a.md", confidence=0.8, methods=["bm25"])]
    b = [SuggestedLink(path="a.md", confidence=0.8, methods=["bm25", "alias"])]
    assert _suggestions_fingerprint(a) != _suggestions_fingerprint(b)


def test_fingerprint_handles_dict_input():
    a = [SuggestedLink(path="a.md", confidence=0.8, methods=["bm25"])]
    b = [{"path": "a.md", "confidence": 0.8, "methods": ["bm25"]}]
    assert _suggestions_fingerprint(a) == _suggestions_fingerprint(b)


# ── Idempotent _finalise ──────────────────────────────────────────


async def test_finalise_skips_write_when_unchanged(ws_db: Path):
    note_rel = "knowledge/idempotent.md"
    full_path = ws_db / "memory" / note_rel
    fm = {
        "title": "x",
        "smart_connect": {
            "version": CURRENT_SMART_CONNECT_VERSION,
            "last_run_at": "2026-04-01T00:00:00Z",
            "last_mode": "fast",
        },
        "suggested_related": [
            {
                "path": "knowledge/other.md",
                "confidence": 0.815,
                "methods": ["bm25", "note_emb"],
            }
        ],
    }
    body = "body content"
    # Pre-write the file so we can detect (no) mtime change.
    from utils.markdown import add_frontmatter
    full_path.write_text(add_frontmatter(body, fm), encoding="utf-8")
    mtime_before = full_path.stat().st_mtime_ns

    suggested = [
        SuggestedLink(
            path="knowledge/other.md", confidence=0.8154,
            methods=["note_emb", "bm25"],
            suggested_at="2026-04-25T12:34:56Z",
        ),
    ]
    result = await _finalise(
        note_rel, ws_db, fm, body, full_path, suggested, mode="fast",
    )
    assert result.unchanged is True
    assert full_path.stat().st_mtime_ns == mtime_before


async def test_finalise_writes_when_force_true(ws_db: Path):
    note_rel = "knowledge/forced.md"
    full_path = ws_db / "memory" / note_rel
    fm = {
        "title": "x",
        "smart_connect": {
            "version": CURRENT_SMART_CONNECT_VERSION,
            "last_run_at": "2026-04-01T00:00:00Z",
            "last_mode": "fast",
        },
        "suggested_related": [
            {"path": "knowledge/other.md", "confidence": 0.8, "methods": ["bm25"]}
        ],
    }
    body = "body"
    from utils.markdown import add_frontmatter
    full_path.write_text(add_frontmatter(body, fm), encoding="utf-8")

    suggested = [
        SuggestedLink(path="knowledge/other.md", confidence=0.8, methods=["bm25"]),
    ]
    result = await _finalise(
        note_rel, ws_db, fm, body, full_path, suggested,
        mode="fast", force=True,
    )
    assert result.unchanged is False


async def test_finalise_writes_when_suggestions_change(ws_db: Path):
    note_rel = "knowledge/changed.md"
    full_path = ws_db / "memory" / note_rel
    fm = {
        "title": "x",
        "smart_connect": {
            "version": CURRENT_SMART_CONNECT_VERSION,
            "last_run_at": "2026-04-01T00:00:00Z",
            "last_mode": "fast",
        },
        "suggested_related": [
            {"path": "a.md", "confidence": 0.8, "methods": ["bm25"]}
        ],
    }
    body = "body"
    from utils.markdown import add_frontmatter
    full_path.write_text(add_frontmatter(body, fm), encoding="utf-8")

    suggested = [
        SuggestedLink(path="b.md", confidence=0.8, methods=["bm25"]),
    ]
    result = await _finalise(
        note_rel, ws_db, fm, body, full_path, suggested, mode="fast",
    )
    assert result.unchanged is False


# ── Coverage endpoint ─────────────────────────────────────────────


async def test_coverage_endpoint_reports_pending_sections(ws_db: Path, monkeypatch):
    import config

    monkeypatch.setattr(config.get_settings(), "workspace_path", ws_db)

    from utils.markdown import add_frontmatter
    mem = ws_db / "memory"
    (mem / "docs").mkdir(parents=True, exist_ok=True)
    (mem / "docs" / "report").mkdir(parents=True, exist_ok=True)

    # Plain note with suggestions.
    (mem / "note-a.md").write_text(
        add_frontmatter(
            "body",
            {"title": "A", "suggested_related": [{"path": "x", "confidence": 0.7, "methods": ["bm25"]}]},
        ),
        encoding="utf-8",
    )
    # Index of a split document.
    (mem / "docs" / "report" / "index.md").write_text(
        add_frontmatter("body", {"title": "Report", "document_type": "pdf-document"}),
        encoding="utf-8",
    )
    # Two pending sections under that index.
    for i in (1, 2):
        (mem / "docs" / "report" / f"{i:02d}-section.md").write_text(
            add_frontmatter(
                "body",
                {
                    "title": f"section {i}",
                    "parent": "docs/report/index.md",
                    "section_index": i,
                },
            ),
            encoding="utf-8",
        )
    # One section that already has suggestions.
    (mem / "docs" / "report" / "03-section.md").write_text(
        add_frontmatter(
            "body",
            {
                "title": "section 3",
                "parent": "docs/report/index.md",
                "section_index": 3,
                "suggested_related": [{"path": "x", "confidence": 0.6, "methods": ["bm25"]}],
            },
        ),
        encoding="utf-8",
    )

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/connections/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sections_total"] == 3
    assert data["sections_with_suggestions"] == 1
    assert data["sections_pending"] == 2
    assert data["documents_pending"] == 1
    assert data["notes_total"] >= 4


# ── Auto-queue helper ─────────────────────────────────────────────


async def test_schedule_section_connect_starts_tracked_job(ws_db: Path):
    from services.ingest_jobs import snapshot

    job_id = schedule_section_connect(
        ["docs/report/01-section.md", "docs/report/02-section.md"],
        workspace_path=ws_db,
        doc_title="Report",
    )
    assert job_id is not None
    snap = snapshot()
    matching = [
        j for j in (snap["active"] + snap["recent"])
        if j["id"] == job_id
    ]
    assert matching, "scheduled job should be tracked in ingest_jobs"
    assert matching[0]["kind"] == "section_connect"


async def test_schedule_section_connect_returns_none_for_empty():
    assert schedule_section_connect([], workspace_path=Path("/tmp")) is None
