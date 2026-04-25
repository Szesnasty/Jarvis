"""Tests for GET /api/connections/stats — Step 26c."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def patch_workspace(ws, monkeypatch):
    monkeypatch.setattr("config.get_settings", lambda: type("S", (), {"workspace_path": ws})())


async def _setup(ws, monkeypatch):
    """Shared setup: init DB, disable heavy deps."""
    from models.database import init_database
    await init_database(ws / "app" / "jarvis.db")
    monkeypatch.setattr("services.entity_extraction.extract_entities", lambda *a, **k: [])
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")


# ---------------------------------------------------------------------------
# Stats endpoint — notes_total
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_stats_notes_total_matches_db(ws, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from main import app
    from services.memory_service import create_note

    await _setup(ws, monkeypatch)
    await create_note("n/a.md", "---\ntitle: A\n---\n\nbody.", ws)
    await create_note("n/b.md", "---\ntitle: B\n---\n\nbody.", ws)
    await create_note("n/c.md", "---\ntitle: C\n---\n\nbody.", ws)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/connections/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes_total"] == 3


# ---------------------------------------------------------------------------
# method_breakdown comes from frontmatter, not alias_index
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_method_breakdown_from_frontmatter(ws, monkeypatch):
    """method_breakdown must count methods from suggested_related frontmatter."""
    from httpx import ASGITransport, AsyncClient
    from main import app
    from services.memory_service import create_note

    await _setup(ws, monkeypatch)

    # Note with two suggestions, both using bm25+alias, one also has note_emb
    content = (
        "---\ntitle: Methodical\n"
        "suggested_related:\n"
        "  - path: n/x.md\n    confidence: 0.82\n    methods: [bm25, alias]\n    tier: strong\n"
        "  - path: n/y.md\n    confidence: 0.70\n    methods: [bm25, note_emb]\n    tier: normal\n"
        "---\n\nbody\n"
    )
    await create_note("n/src.md", content, ws)
    await create_note("n/x.md", "---\ntitle: X\n---\n\nbody.", ws)
    await create_note("n/y.md", "---\ntitle: Y\n---\n\nbody.", ws)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/connections/stats")
    data = resp.json()
    mb = data["method_breakdown"]

    # bm25 appears twice (both suggestions), alias once, note_emb once
    assert mb.get("bm25", 0) == 2
    assert mb.get("alias", 0) == 1
    assert mb.get("note_emb", 0) == 1
    # Total suggestions = 2 (one per suggestion per method count sums to 4 method-occurrences)
    assert data["suggestions_total"] == 4


# ---------------------------------------------------------------------------
# Orphan accounting
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_orphan_with_and_without_suggestions(ws, monkeypatch):
    """semantic_orphans_with + _without must equal semantic_orphans_total."""
    from httpx import ASGITransport, AsyncClient
    from main import app
    from services.memory_service import create_note

    await _setup(ws, monkeypatch)
    await create_note("o/lone.md", "---\ntitle: Lone\n---\n\njust body.", ws)
    await create_note("o/x.md", "---\ntitle: X\n---\n\nbody.", ws)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/connections/stats")
    data = resp.json()
    assert (
        data["semantic_orphans_with_suggestions"] + data["semantic_orphans_without_suggestions"]
        == data["semantic_orphans_total"]
    )


# ---------------------------------------------------------------------------
# Event aggregation
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_acceptance_rate_null_when_no_events(ws, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from main import app
    from services.memory_service import create_note

    await _setup(ws, monkeypatch)
    await create_note("r/a.md", "---\ntitle: A\n---\n\nbody.", ws)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/connections/stats")
    data = resp.json()
    assert data["events"]["acceptance_rate"] is None


@pytest.mark.anyio
async def test_acceptance_rate_from_events(ws, monkeypatch):
    """acceptance_rate = promoted / (promoted + dismissed)."""
    from httpx import ASGITransport, AsyncClient
    from main import app
    from services.connection_events import write_event
    from services.memory_service import _db_path, create_note

    await _setup(ws, monkeypatch)
    await create_note("r/a.md", "---\ntitle: A\n---\n\nbody.", ws)
    db_p = _db_path(ws)

    # 3 promotes, 1 dismiss → rate = 3/(3+1) = 0.75
    for i in range(3):
        write_event(db_p, event_type="promote", note_path=f"r/{i}.md")
    write_event(db_p, event_type="dismiss", note_path="r/x.md")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/connections/stats")
    data = resp.json()
    assert abs(data["events"]["acceptance_rate"] - 0.75) < 0.001
    assert data["events"]["promoted_total"] == 3
    assert data["events"]["dismissed_total"] == 1


@pytest.mark.anyio
async def test_promoted_by_method_aggregation(ws, monkeypatch):
    """promoted_by_method counts promoted events per method."""
    from httpx import ASGITransport, AsyncClient
    from main import app
    from services.connection_events import write_event
    from services.memory_service import _db_path, create_note

    await _setup(ws, monkeypatch)
    await create_note("s/a.md", "---\ntitle: A\n---\n\nbody.", ws)
    db_p = _db_path(ws)

    write_event(db_p, event_type="promote", note_path="s/1.md", methods=["bm25", "alias"])
    write_event(db_p, event_type="promote", note_path="s/2.md", methods=["alias"])
    write_event(db_p, event_type="dismiss", note_path="s/3.md", methods=["bm25"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/connections/stats")
    data = resp.json()
    pbm = data["events"]["promoted_by_method"]
    assert pbm.get("alias", 0) == 2  # alias in both promotes
    assert pbm.get("bm25", 0) == 1   # bm25 only in first promote
    dbm = data["events"]["dismissed_by_method"]
    assert dbm.get("bm25", 0) == 1
