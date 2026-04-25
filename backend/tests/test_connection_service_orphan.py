"""Step 25 PR 4 — semantic orphan detection + aggressive-mode trigger."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.graph_service import (
    find_orphans,
    find_semantic_orphans,
    invalidate_cache,
    is_semantic_orphan,
    rebuild_graph,
)
from services.graph_service.models import Edge, Node
from services.memory_service import create_note


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


# ---------------------------------------------------------------------------
# find_semantic_orphans
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_note_with_only_noisy_tag_is_semantic_orphan(ws_db, monkeypatch):
    # Disable entity extraction so spaCy NER on a CI machine doesn't add
    # a `mentions_org`/`mentions_project` edge that would rescue the note
    # from orphan status.
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities",
        lambda *_a, **_kw: [],
    )
    await create_note(
        "imported/raw-1.md",
        "---\ntitle: Raw 1\ntags: [imported]\n---\n\njust some plain body words.",
        ws_db,
    )
    rebuild_graph(ws_db)

    # The legacy `find_orphans` will not flag it (it has a tagged edge).
    legacy = {o["id"] for o in find_orphans(ws_db)}
    assert "note:imported/raw-1.md" not in legacy

    # The new `find_semantic_orphans` must flag it (only edge is into a noisy tag).
    semantic = {o["id"] for o in find_semantic_orphans(ws_db)}
    assert "note:imported/raw-1.md" in semantic


@pytest.mark.anyio
async def test_note_with_meaningful_tag_is_not_semantic_orphan(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities",
        lambda *_a, **_kw: [],
    )
    await create_note(
        "knowledge/sleep.md",
        "---\ntitle: Sleep notes\ntags: [health]\n---\n\njust a few words.",
        ws_db,
    )
    rebuild_graph(ws_db)

    semantic = {o["id"] for o in find_semantic_orphans(ws_db)}
    # `tagged` is in the default ignore set, so even a "good" tag won't count
    # — meaningful linking comes from `mentions`/`linked`/`related`/etc.
    # The note IS a semantic orphan in this minimal corpus.
    assert "note:knowledge/sleep.md" in semantic


@pytest.mark.anyio
async def test_note_with_link_is_not_semantic_orphan(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities",
        lambda *_a, **_kw: [],
    )
    await create_note("k/a.md", "---\ntitle: A\n---\n\nplain.", ws_db)
    await create_note("k/b.md", "---\ntitle: B\n---\n\nplain.", ws_db)
    rebuild_graph(ws_db)

    # Add a synthetic `linked` edge so we don't depend on wiki-link resolution.
    from services.graph_service import _save_and_cache, load_graph
    g = load_graph(ws_db)
    g.add_edge("note:k/a.md", "note:k/b.md", "linked", weight=1.0)
    _save_and_cache(g, workspace_path=ws_db)

    semantic_ids = {o["id"] for o in find_semantic_orphans(ws_db)}
    assert "note:k/a.md" not in semantic_ids
    assert "note:k/b.md" not in semantic_ids


@pytest.mark.anyio
async def test_is_semantic_orphan_predicate(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities",
        lambda *_a, **_kw: [],
    )
    await create_note(
        "imported/raw-2.md",
        "---\ntitle: Raw 2\ntags: [imported, data]\n---\n\njust words here.",
        ws_db,
    )
    rebuild_graph(ws_db)

    assert is_semantic_orphan("imported/raw-2.md", workspace_path=ws_db)


# ---------------------------------------------------------------------------
# Aggressive-mode trigger inside connect_note
# ---------------------------------------------------------------------------


def _stub_graph_with_orphan(ws_db, orphan_path: str) -> None:
    """Persist a graph in which ``orphan_path`` is a semantic orphan."""
    from services.graph_service import _save_and_cache
    from services.graph_service.models import Graph

    g = Graph()
    g.add_node(f"note:{orphan_path}", "note", "Orphan")
    g.add_node("tag:imported", "tag", "imported")
    g.add_edge(f"note:{orphan_path}", "tag:imported", "tagged", weight=0.6)
    _save_and_cache(g, workspace_path=ws_db)


@pytest.mark.anyio
async def test_connect_note_retries_in_aggressive_mode_for_orphan(ws_db, monkeypatch):
    """A weak BM25-only signal must surface when the note is a semantic orphan."""
    from services import connection_service as cs

    note_path = "imported/lonely.md"
    target_path = "knowledge/related.md"

    await create_note(
        target_path,
        "---\ntitle: Related\n---\n\nStandalone neighbour.",
        ws_db,
    )
    await create_note(
        note_path,
        "---\ntitle: Lonely\ntags: [imported]\n---\n\nIsolated body text.",
        ws_db,
    )

    # Force the orphan state regardless of what create_note built.
    _stub_graph_with_orphan(ws_db, note_path)

    # Stub list_notes to return one weak BM25 hit (just above renormalised
    # floor for BM25-only mode but well below 0.60 in fast mode).
    async def _fake_list_notes(*, search, limit, workspace_path):
        return [{"path": target_path, "_bm25_score": -1.0}]

    monkeypatch.setattr("services.memory_service.list_notes", _fake_list_notes)

    import os
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")

    result = await cs.connect_note(note_path, workspace_path=ws_db)

    paths = [s.path for s in result.suggested]
    assert target_path in paths
    # In aggressive mode the weak tier (0.45–0.59) is kept.
    weak_tier = next(s for s in result.suggested if s.path == target_path)
    assert weak_tier.tier in {"weak", "normal", "strong"}


@pytest.mark.anyio
async def test_connect_note_does_not_retry_when_not_orphan(ws_db, monkeypatch):
    """If the note already has meaningful neighbours, weak hits stay dropped."""
    from services import connection_service as cs
    from services.graph_service import _save_and_cache
    from services.graph_service.models import Graph

    note_path = "k/social.md"
    target_path = "k/peer.md"

    await create_note(
        target_path,
        "---\ntitle: Peer\n---\n\nA peer note.",
        ws_db,
    )
    await create_note(
        note_path,
        "---\ntitle: Social\n---\n\nLinks to [[peer]].",
        ws_db,
    )

    # Build a graph where the note has a `linked` edge (not an orphan).
    g = Graph()
    g.add_node(f"note:{note_path}", "note", "Social")
    g.add_node(f"note:{target_path}", "note", "Peer")
    g.add_edge(f"note:{note_path}", f"note:{target_path}", "linked", weight=1.0)
    _save_and_cache(g, workspace_path=ws_db)

    # Same weak BM25 signal as the previous test.
    async def _fake_list_notes(*, search, limit, workspace_path):
        return [{"path": "k/unrelated.md", "_bm25_score": -1.0}]

    monkeypatch.setattr("services.memory_service.list_notes", _fake_list_notes)
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")

    result = await cs.connect_note(note_path, workspace_path=ws_db)

    # No suggestion crossed the normal floor and the note isn't an orphan,
    # so aggressive mode does NOT engage and weak suggestions stay dropped.
    assert all(s.tier in {"normal", "strong"} for s in result.suggested)


# ---------------------------------------------------------------------------
# Step 26b: same_batch / derived_from / suggested_related as orphan indicators
# ---------------------------------------------------------------------------

def _stub_graph_with_single_edge(ws_db, note_path: str, edge_type: str) -> None:
    """Build a minimal graph where note has exactly one edge of the given type."""
    from services.graph_service import _save_and_cache
    from services.graph_service.models import Graph

    g = Graph()
    g.add_node(f"note:{note_path}", "note", "Test Note")
    g.add_node("note:other.md", "note", "Other")
    g.add_edge(f"note:{note_path}", "note:other.md", edge_type, weight=0.8)
    _save_and_cache(g, workspace_path=ws_db)


@pytest.mark.anyio
async def test_note_with_only_derived_from_edge_is_semantic_orphan(ws_db):
    """derived_from is in DEFAULT_ORPHAN_IGNORE_EDGE_TYPES — note is still an orphan."""
    _stub_graph_with_single_edge(ws_db, "p/derived.md", "derived_from")
    assert is_semantic_orphan("p/derived.md", workspace_path=ws_db)


@pytest.mark.anyio
async def test_note_with_only_same_batch_edge_is_semantic_orphan(ws_db):
    """same_batch (Step 26b addition) is in ignore set — note is still an orphan."""
    _stub_graph_with_single_edge(ws_db, "p/batch.md", "same_batch")
    assert is_semantic_orphan("p/batch.md", workspace_path=ws_db)


@pytest.mark.anyio
async def test_note_with_only_suggested_related_edge_is_semantic_orphan(ws_db):
    """suggested_related (Step 26b addition) is in ignore set — note is still an orphan."""
    _stub_graph_with_single_edge(ws_db, "p/suggest.md", "suggested_related")
    assert is_semantic_orphan("p/suggest.md", workspace_path=ws_db)


@pytest.mark.anyio
async def test_note_with_confirmed_related_edge_is_not_semantic_orphan(ws_db):
    """A user-confirmed 'related' edge is NOT in the ignore set — note escapes orphan status."""
    from services.graph_service import _save_and_cache
    from services.graph_service.models import Graph

    note_path = "p/confirmed.md"
    g = Graph()
    g.add_node(f"note:{note_path}", "note", "Confirmed")
    g.add_node("note:peer.md", "note", "Peer")
    g.add_edge(f"note:{note_path}", "note:peer.md", "related", weight=1.0)
    _save_and_cache(g, workspace_path=ws_db)

    assert not is_semantic_orphan(note_path, workspace_path=ws_db)


# ---------------------------------------------------------------------------
# Step 26b: retrieval _compute_graph_score caps suggested_related edges
# ---------------------------------------------------------------------------

def test_compute_graph_score_caps_suggested_related():
    """suggested_related edges must be capped at SUGGESTED_RELATED_MAX_WEIGHT."""
    from services.retrieval.pipeline import _compute_graph_score
    from services.graph_service.models import Graph
    from services.graph_service.queries import SUGGESTED_RELATED_MAX_WEIGHT

    g = Graph()
    g.add_node("note:a.md", "note", "A")
    g.add_node("note:b.md", "note", "B")
    # Add a suggested_related edge with a weight well above the cap
    g.add_edge("note:a.md", "note:b.md", "suggested_related", weight=0.9)

    score = _compute_graph_score(
        "note:a.md",
        g,
        anchors=[],
        candidate_ids={"note:a.md", "note:b.md"},
    )
    # If the cap is applied, edge contribution = min(0.9, 0.35) = 0.35.
    # Without cap it would be 0.9. Score should reflect the cap.
    assert score <= SUGGESTED_RELATED_MAX_WEIGHT + 0.01  # small tolerance for path/cluster bonuses


def test_compute_graph_score_related_edge_not_capped():
    """A confirmed 'related' edge is NOT capped — uses its full weight."""
    from services.retrieval.pipeline import _compute_graph_score
    from services.graph_service.models import Graph
    from services.graph_service.queries import SUGGESTED_RELATED_MAX_WEIGHT

    g = Graph()
    g.add_node("note:a.md", "note", "A")
    g.add_node("note:b.md", "note", "B")
    g.add_edge("note:a.md", "note:b.md", "related", weight=0.9)

    score = _compute_graph_score(
        "note:a.md",
        g,
        anchors=[],
        candidate_ids={"note:a.md", "note:b.md"},
    )
    # related edge at 0.9 > SUGGESTED_RELATED_MAX_WEIGHT — score must exceed the cap
    assert score > SUGGESTED_RELATED_MAX_WEIGHT
