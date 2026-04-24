"""Step 25 PR 2 — graph entity expansion: org/project/place edges.

Both ``rebuild_graph`` (full pass) and ``ingest_note`` (incremental) must
emit nodes and edges for the broader entity types via the shared helper
``services.graph_service.entity_edges.apply_extracted_entities``.

We monkeypatch ``extract_entities`` so the test does not depend on spaCy
model availability in CI.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.entity_extraction import ExtractedEntity
from services.graph_service import ingest_note, invalidate_cache, rebuild_graph
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


def _fixed_entities(_text, _existing=None):
    """Deterministic stand-in for the spaCy/regex extractor."""
    return [
        ExtractedEntity(text="Alice Kowalska", type="person", confidence=0.9),
        ExtractedEntity(text="Anthropic", type="organization", confidence=0.85),
        ExtractedEntity(text="Jarvis", type="project", confidence=0.7),
        ExtractedEntity(text="Warszawa", type="place", confidence=0.65),
        ExtractedEntity(text="2026-04-24", type="date", confidence=0.95),
    ]


@pytest.mark.anyio
async def test_rebuild_graph_emits_org_project_place(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", _fixed_entities,
    )
    await create_note(
        "knowledge/intro.md",
        "---\ntitle: Intro\n---\n\nSome body about the project and the team.",
        ws_db,
    )
    graph = rebuild_graph(ws_db)

    types = {n.type for n in graph.nodes.values()}
    assert {"person", "org", "project", "place"}.issubset(types)
    # Dates must NOT become graph nodes (spec §3 — temporal handled separately)
    assert "date" not in types

    edge_types = {e.type for e in graph.edges}
    assert {"mentions", "mentions_org", "mentions_project", "mentions_place"}.issubset(
        edge_types
    )


@pytest.mark.anyio
async def test_ingest_note_emits_org_project_place(ws_db, monkeypatch):
    """Incremental path stays in sync with the full rebuild."""
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", _fixed_entities,
    )
    await create_note(
        "knowledge/intro.md",
        "---\ntitle: Intro\n---\n\nBody.",
        ws_db,
    )
    # Seed graph with one rebuild (so ingest_note has a base to merge into).
    rebuild_graph(ws_db)
    invalidate_cache()

    ingest_note("knowledge/intro.md", workspace_path=ws_db)

    from services.graph_service import load_graph

    graph = load_graph(ws_db)
    assert graph is not None
    types = {n.type for n in graph.nodes.values()}
    assert {"person", "org", "project", "place"}.issubset(types)
    edge_types = {e.type for e in graph.edges}
    assert {"mentions_org", "mentions_project", "mentions_place"}.issubset(edge_types)


@pytest.mark.anyio
async def test_entity_edges_use_configured_weights(ws_db, monkeypatch):
    """Edge base weights for the new types match the spec (§3)."""
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", _fixed_entities,
    )
    await create_note(
        "knowledge/intro.md",
        "---\ntitle: Intro\n---\n\nBody.",
        ws_db,
    )
    graph = rebuild_graph(ws_db)

    weight_by_type = {e.type: e.weight for e in graph.edges}
    assert weight_by_type.get("mentions_org") == pytest.approx(0.55)
    assert weight_by_type.get("mentions_project") == pytest.approx(0.70)
    assert weight_by_type.get("mentions_place") == pytest.approx(0.35)


@pytest.mark.anyio
async def test_frontmatter_orgs_suppress_duplicate_edge(ws_db, monkeypatch):
    """Org named in frontmatter ``organizations`` is not re-added by NER."""
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities",
        lambda _t, _e=None: [
            ExtractedEntity(text="Anthropic", type="organization", confidence=0.9),
        ],
    )
    await create_note(
        "knowledge/intro.md",
        "---\ntitle: Intro\norganizations: [Anthropic]\n---\n\nBody.",
        ws_db,
    )
    graph = rebuild_graph(ws_db)

    org_edges = [
        e for e in graph.edges
        if e.type == "mentions_org" and e.target == "org:Anthropic"
    ]
    # The frontmatter declaration suppresses the duplicate NER edge.
    assert len(org_edges) == 0
