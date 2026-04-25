"""Tests for score_breakdown and suggested_at/suggested_by fields — Step 26c."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from services.connection_service import (
    CURRENT_SMART_CONNECT_VERSION,
    W_ALIAS,
    W_BM25,
    W_NOTE_EMB,
    _compute_score_breakdown,
    _merge_candidates,
    score_candidate,
)


# ---------------------------------------------------------------------------
# _compute_score_breakdown — unit tests
# ---------------------------------------------------------------------------

class TestScoreBreakdown:
    def test_two_signals_returns_breakdown(self):
        bm25 = {"a.md": 0.8}
        note_emb = {"a.md": 0.7}
        chunk_emb: dict = {}
        alias = None
        active_weight_sum = W_BM25 + W_NOTE_EMB  # 0.30 + 0.30 = 0.60

        bd = _compute_score_breakdown("a.md", bm25, note_emb, chunk_emb, alias, active_weight_sum)
        assert bd is not None
        assert "bm25" in bd
        assert "note_emb" in bd

    def test_one_signal_returns_none(self):
        bm25 = {"a.md": 0.8}
        active_weight_sum = W_BM25

        bd = _compute_score_breakdown("a.md", bm25, {}, {}, None, active_weight_sum)
        assert bd is None

    def test_breakdown_sums_to_confidence(self):
        bm25 = {"a.md": 0.8}
        note_emb = {"a.md": 0.6}
        alias = {"a.md": (1.0, "smart connect")}
        active_weight_sum = W_BM25 + W_NOTE_EMB + W_ALIAS

        bd = _compute_score_breakdown("a.md", bm25, note_emb, {}, alias, active_weight_sum)
        assert bd is not None

        # Compute expected confidence via score_candidate
        raw = score_candidate(bm25=0.8, note_emb=0.6, alias=1.0)
        confidence = round(raw / active_weight_sum, 3)

        total = round(sum(bd.values()), 3)
        assert abs(total - confidence) <= 0.001, f"{total} != {confidence}, breakdown={bd}"

    def test_three_signals_no_alias_breakdown_sums(self):
        bm25 = {"x.md": 1.0}
        note_emb = {"x.md": 0.9}
        chunk_emb = {"x.md": (0.8, "intro")}
        from services.connection_service import W_CHUNK_EMB
        active_weight_sum = W_BM25 + W_NOTE_EMB + W_CHUNK_EMB

        bd = _compute_score_breakdown("x.md", bm25, note_emb, chunk_emb, None, active_weight_sum)
        assert bd is not None
        assert len(bd) == 3

        raw = score_candidate(bm25=1.0, note_emb=0.9, chunk_emb=0.8)
        confidence = round(raw / active_weight_sum, 3)
        total = round(sum(bd.values()), 3)
        assert abs(total - confidence) <= 0.001

    def test_breakdown_values_are_positive(self):
        bm25 = {"b.md": 0.5}
        note_emb = {"b.md": 0.4}
        active_weight_sum = W_BM25 + W_NOTE_EMB

        bd = _compute_score_breakdown("b.md", bm25, note_emb, {}, None, active_weight_sum)
        assert bd is not None
        assert all(v > 0 for v in bd.values())

    def test_absent_path_returns_none(self):
        active_weight_sum = W_BM25
        bd = _compute_score_breakdown("missing.md", {"other.md": 0.9}, {}, {}, None, active_weight_sum)
        # Only one signal fires (bm25=0 for "missing.md", so zero active signals)
        assert bd is None


# ---------------------------------------------------------------------------
# Integration: SuggestedLink carries score_breakdown + suggested_at + suggested_by
# ---------------------------------------------------------------------------

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


@pytest.mark.anyio
async def test_suggested_at_is_valid_iso8601(ws, monkeypatch):
    """SuggestedLink.suggested_at must be a valid ISO-8601 UTC timestamp."""
    from models.database import init_database
    from services.connection_service import generate_suggestions
    from services.memory_service import create_note

    await init_database(ws / "app" / "jarvis.db")
    monkeypatch.setattr("services.entity_extraction.extract_entities", lambda *a, **k: [])
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")

    # Create two notes so BM25 has something to return
    await create_note("k/a.md", "---\ntitle: Alpha retrieval\n---\n\nRetrieval pipeline.", ws)
    await create_note("k/b.md", "---\ntitle: Beta retrieval\n---\n\nSame retrieval text.", ws)

    # Stub BM25 to return a hit
    async def _fake_list_notes(*, search, limit, workspace_path):
        return [{"path": "k/b.md", "_bm25_score": -2.0}]

    monkeypatch.setattr("services.memory_service.list_notes", _fake_list_notes)

    ctx = await generate_suggestions("k/a.md", workspace_path=ws)
    for s in ctx.suggestions:
        assert s.suggested_at is not None
        # Validate ISO-8601 format: 2026-04-27T14:32:00Z
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s.suggested_at), (
            f"suggested_at not ISO-8601: {s.suggested_at}"
        )


@pytest.mark.anyio
async def test_suggested_by_includes_version(ws, monkeypatch):
    """SuggestedLink.suggested_by must equal smart_connect_v{VERSION}."""
    from models.database import init_database
    from services.connection_service import generate_suggestions
    from services.memory_service import create_note

    await init_database(ws / "app" / "jarvis.db")
    monkeypatch.setattr("services.entity_extraction.extract_entities", lambda *a, **k: [])
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")

    await create_note("k/c.md", "---\ntitle: Gamma\n---\n\nSomething.", ws)
    await create_note("k/d.md", "---\ntitle: Delta\n---\n\nSomething.", ws)

    async def _fake_list_notes(*, search, limit, workspace_path):
        return [{"path": "k/d.md", "_bm25_score": -2.0}]

    monkeypatch.setattr("services.memory_service.list_notes", _fake_list_notes)

    ctx = await generate_suggestions("k/c.md", workspace_path=ws)
    expected = f"smart_connect_v{CURRENT_SMART_CONNECT_VERSION}"
    for s in ctx.suggestions:
        assert s.suggested_by == expected


@pytest.mark.anyio
async def test_score_breakdown_absent_for_single_method(ws, monkeypatch):
    """score_breakdown must be None when only one method fires."""
    from models.database import init_database
    from services.connection_service import generate_suggestions
    from services.memory_service import create_note

    await init_database(ws / "app" / "jarvis.db")
    monkeypatch.setattr("services.entity_extraction.extract_entities", lambda *a, **k: [])
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")

    await create_note("k/e.md", "---\ntitle: Epsilon\n---\n\nSomething.", ws)
    await create_note("k/f.md", "---\ntitle: Zeta\n---\n\nSomething.", ws)

    # Only BM25 fires (embeddings disabled, no alias match)
    async def _fake_list_notes(*, search, limit, workspace_path):
        return [{"path": "k/f.md", "_bm25_score": -1.5}]

    monkeypatch.setattr("services.memory_service.list_notes", _fake_list_notes)

    ctx = await generate_suggestions("k/e.md", workspace_path=ws, mode="aggressive")
    # When only BM25 fires, score_breakdown should be None
    for s in ctx.suggestions:
        if s.methods == ["bm25"]:
            assert s.score_breakdown is None
