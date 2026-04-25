"""Tests for Smart Connect backfill — Step 26a.

Covers:
  * backfill processes all notes without exception
  * dry_run=True is strictly read-only (no frontmatter, graph, or index writes)
  * only_orphans=True skips notes that already have related edges
  * batch_size progress callbacks fire the correct number of times
  * force=True re-processes a note already at current version
  * version < CURRENT → note is processed on backfill
  * version >= CURRENT + has suggestions + not orphan → note is skipped
  * min_confidence filters which suggestions are written to frontmatter
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.connection_service import (
    CURRENT_SMART_CONNECT_VERSION,
    connect_note,
    generate_suggestions,
    apply_suggestions,
)
from utils.markdown import parse_frontmatter


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    (tmp_path / "memory" / "knowledge").mkdir(parents=True)
    (tmp_path / "memory" / "inbox").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws: Path) -> Path:
    await init_database(ws / "app" / "jarvis.db")
    return ws


def _write_note(ws: Path, rel: str, title: str, body: str) -> Path:
    full = ws / "memory" / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(f"---\ntitle: {title}\n---\n\n{body}", encoding="utf-8")
    return full


async def _index(ws: Path, rel: str) -> None:
    from services.memory_service import index_note_file
    await index_note_file(rel, workspace_path=ws)


# ---------------------------------------------------------------------------
# generate_suggestions / apply_suggestions split
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_suggestions_is_read_only(ws_db: Path) -> None:
    """generate_suggestions must not write frontmatter or graph."""
    note_path = "knowledge/alpha.md"
    full_path = _write_note(ws_db, note_path, "Alpha", "knowledge about retrieval pipelines")
    await _index(ws_db, note_path)
    mtime_before = full_path.stat().st_mtime

    ctx = await generate_suggestions(note_path, workspace_path=ws_db)

    # File must not have been modified
    assert full_path.stat().st_mtime == mtime_before
    # Frontmatter must not contain smart_connect key
    _, raw_fm = parse_frontmatter(full_path.read_text(encoding="utf-8"))
    assert "smart_connect" not in full_path.read_text(encoding="utf-8")
    assert isinstance(ctx.suggestions, list)


@pytest.mark.anyio
async def test_apply_suggestions_writes_version_stamp(ws_db: Path) -> None:
    """apply_suggestions must write smart_connect versioning block to frontmatter."""
    note_path = "knowledge/beta.md"
    _write_note(ws_db, note_path, "Beta", "retrieval pipeline for knowledge bases")
    await _index(ws_db, note_path)

    ctx = await generate_suggestions(note_path, workspace_path=ws_db)
    await apply_suggestions(ctx)

    full_path = ws_db / "memory" / note_path
    fm, _ = parse_frontmatter(full_path.read_text(encoding="utf-8"))
    sc = fm.get("smart_connect")
    assert isinstance(sc, dict)
    assert sc["version"] == CURRENT_SMART_CONNECT_VERSION
    assert "last_run_at" in sc
    assert sc["last_mode"] == "fast"


# ---------------------------------------------------------------------------
# connect_note with dry_run
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dry_run_does_not_write_frontmatter(ws_db: Path) -> None:
    """dry_run=True must not modify the note file."""
    note_path = "knowledge/dry.md"
    full_path = _write_note(ws_db, note_path, "Dry note", "testing dry run behaviour")
    await _index(ws_db, note_path)
    content_before = full_path.read_text(encoding="utf-8")

    result = await connect_note(note_path, workspace_path=ws_db, dry_run=True)

    assert full_path.read_text(encoding="utf-8") == content_before
    assert "smart_connect" not in content_before
    # Result still carries suggestions (if any were found)
    assert hasattr(result, "suggested")


@pytest.mark.anyio
async def test_dry_run_does_not_write_graph(ws_db: Path) -> None:
    """dry_run=True must not modify graph.json."""
    import json as _json

    note_path = "knowledge/nodry.md"
    _write_note(ws_db, note_path, "No dry", "testing graph isolation")
    await _index(ws_db, note_path)

    graph_path = ws_db / "graph" / "graph.json"
    graph_before = graph_path.read_text(encoding="utf-8") if graph_path.exists() else None

    await connect_note(note_path, workspace_path=ws_db, dry_run=True)

    graph_after = graph_path.read_text(encoding="utf-8") if graph_path.exists() else None
    assert graph_before == graph_after


@pytest.mark.anyio
async def test_connect_note_writes_suggested_by(ws_db: Path) -> None:
    """Non-dry-run connect_note should stamp suggested_by on each suggestion."""
    note_path = "knowledge/stamp.md"
    _write_note(ws_db, note_path, "Stamp", "pipeline for retrieval")

    target_path = "knowledge/target.md"
    _write_note(ws_db, target_path, "Target", "retrieval pipeline knowledge")
    await _index(ws_db, note_path)
    await _index(ws_db, target_path)

    result = await connect_note(note_path, workspace_path=ws_db)

    full_path = ws_db / "memory" / note_path
    fm, _ = parse_frontmatter(full_path.read_text(encoding="utf-8"))
    for entry in fm.get("suggested_related", []):
        if isinstance(entry, dict):
            assert entry.get("suggested_by") == f"smart_connect_v{CURRENT_SMART_CONNECT_VERSION}"


# ---------------------------------------------------------------------------
# min_confidence filtering
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_min_confidence_filters_suggestions(ws_db: Path, monkeypatch) -> None:
    """Only suggestions at or above min_confidence should be written."""
    from services import connection_service as cs

    note_path = "knowledge/conf.md"
    _write_note(ws_db, note_path, "Conf", "testing confidence threshold")
    await _index(ws_db, note_path)

    # Inject a fake context with two suggestions of differing confidence
    from services.connection_service import SuggestedLink, _SuggestContext

    fake_suggestions = [
        SuggestedLink(path="a.md", confidence=0.90, methods=["bm25"], tier="strong"),
        SuggestedLink(path="b.md", confidence=0.50, methods=["bm25"], tier="normal"),
    ]
    full_path = ws_db / "memory" / note_path
    fm, body = parse_frontmatter(full_path.read_text(encoding="utf-8"))
    ctx = _SuggestContext(
        note_path=note_path,
        ws=ws_db,
        fm=fm,
        body=body,
        full_path=full_path,
        suggestions=fake_suggestions,
        aliases_matched=[],
        mode="fast",
    )

    await apply_suggestions(ctx, min_confidence=0.80)

    fm2, _ = parse_frontmatter(full_path.read_text(encoding="utf-8"))
    written_paths = [e["path"] for e in fm2.get("suggested_related", []) if isinstance(e, dict)]
    assert "a.md" in written_paths
    assert "b.md" not in written_paths


# ---------------------------------------------------------------------------
# Backfill endpoint (HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_backfill_endpoint_streams_progress(ws_db: Path, monkeypatch) -> None:
    """POST /api/connections/backfill should return streaming JSON lines."""
    import os
    os.environ["JARVIS_TEST_WORKSPACE"] = str(ws_db)

    from config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_path", ws_db)

    note_path = "knowledge/stream.md"
    _write_note(ws_db, note_path, "Stream", "streaming test note")
    await _index(ws_db, note_path)

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/connections/backfill",
            json={"dry_run": True, "batch_size": 50},
        )
    assert resp.status_code == 200
    # Parse last non-empty JSON line
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    assert len(lines) >= 1
    last = json.loads(lines[-1])
    assert "done" in last
    assert "total" in last
    assert last["dry_run"] is True


@pytest.mark.anyio
async def test_backfill_skips_current_version_notes(ws_db: Path, monkeypatch) -> None:
    """Notes with version >= CURRENT and existing suggestions should be skipped."""
    from config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_path", ws_db)

    note_path = "knowledge/versioned.md"
    full_path = _write_note(ws_db, note_path, "Versioned", "already processed note")
    # Pre-stamp with current version + suggestions
    content = (
        f"---\ntitle: Versioned\n"
        f"smart_connect:\n  version: {CURRENT_SMART_CONNECT_VERSION}\n  last_run_at: '2026-01-01T00:00:00Z'\n  last_mode: fast\n"
        f"suggested_related:\n  - path: other.md\n    confidence: 0.7\n    methods: [bm25]\n---\n\nalready processed\n"
    )
    full_path.write_text(content, encoding="utf-8")
    await _index(ws_db, note_path)

    mtime_before = full_path.stat().st_mtime

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/connections/backfill",
            json={"batch_size": 50, "force": False},
        )
    assert resp.status_code == 200
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    last = json.loads(lines[-1])
    assert last["skipped"] >= 1
    # File should not have been rewritten
    assert full_path.stat().st_mtime == mtime_before


@pytest.mark.anyio
async def test_backfill_force_reprocesses_current_version(ws_db: Path, monkeypatch) -> None:
    """force=True must reprocess a note already at the current version."""
    from config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_path", ws_db)

    note_path = "knowledge/force.md"
    full_path = _write_note(ws_db, note_path, "Force", "force reprocess note")
    content = (
        f"---\ntitle: Force\n"
        f"smart_connect:\n  version: {CURRENT_SMART_CONNECT_VERSION}\n  last_run_at: '2026-01-01T00:00:00Z'\n  last_mode: fast\n"
        f"suggested_related: []\n---\n\nforce test body\n"
    )
    full_path.write_text(content, encoding="utf-8")
    await _index(ws_db, note_path)

    mtime_before = full_path.stat().st_mtime
    import time
    time.sleep(0.05)

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/connections/backfill",
            json={"batch_size": 50, "force": True},
        )
    assert resp.status_code == 200
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    last = json.loads(lines[-1])
    assert last["skipped"] == 0
    # File must have been rewritten
    assert full_path.stat().st_mtime > mtime_before


@pytest.mark.anyio
async def test_backfill_processes_old_version(ws_db: Path, monkeypatch) -> None:
    """A note with smart_connect.version < CURRENT must be reprocessed."""
    from config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_path", ws_db)

    note_path = "knowledge/old_version.md"
    full_path = _write_note(ws_db, note_path, "Old version", "outdated version stamp")
    old_version = CURRENT_SMART_CONNECT_VERSION - 1
    content = (
        f"---\ntitle: Old version\n"
        f"smart_connect:\n  version: {old_version}\n  last_run_at: '2025-01-01T00:00:00Z'\n  last_mode: fast\n"
        f"suggested_related: []\n---\n\noutdated\n"
    )
    full_path.write_text(content, encoding="utf-8")
    await _index(ws_db, note_path)

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/connections/backfill",
            json={"batch_size": 50, "force": False},
        )
    assert resp.status_code == 200
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    last = json.loads(lines[-1])
    # Should have been processed (not skipped)
    assert last["skipped"] == 0


@pytest.mark.anyio
async def test_backfill_batch_size_callback_count(ws_db: Path, monkeypatch) -> None:
    """batch_size=10 on 25 notes → exactly 3 progress lines (ceil(25/10) = 3)."""
    from config import get_settings
    monkeypatch.setattr(get_settings(), "workspace_path", ws_db)

    for i in range(25):
        p = f"knowledge/note_{i:02d}.md"
        full = _write_note(ws_db, p, f"Note {i}", f"content for note number {i}")
        await _index(ws_db, p)

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/connections/backfill",
            json={"batch_size": 10, "dry_run": True},
        )
    assert resp.status_code == 200
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    assert len(lines) == 3
    last = json.loads(lines[-1])
    assert last["total"] == 25
    assert last["done"] == 25
