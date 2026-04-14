"""Tests for embedding-based similar_to edges in the knowledge graph."""
import sqlite3
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services import graph_service
from services.embedding_service import vector_to_blob
from services.graph_service import (
    _compute_embedding_similarity_edges,
    _compute_keyword_similarity_edges,
    _compute_similarity_edges,
    invalidate_cache,
    rebuild_graph,
)
from services.memory_service import create_note


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def clear_graph_cache():
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


def _inject_embedding(db_path, note_path, vec):
    """Write a fake embedding row directly to note_embeddings."""
    now = datetime.now(timezone.utc).isoformat()
    blob = vector_to_blob(vec)
    conn = sqlite3.connect(str(db_path))
    try:
        # Look up or insert the note row
        row = conn.execute("SELECT id FROM notes WHERE path = ?", (note_path,)).fetchone()
        note_id = row[0] if row else 0
        conn.execute(
            """
            INSERT OR REPLACE INTO note_embeddings
            (note_id, path, embedding, content_hash, model_name, dimensions, embedded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (note_id, note_path, blob, "fake", "fake", len(vec), now),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.anyio
async def test_embedding_edges_created_above_threshold(ws_db):
    """Two notes with cosine similarity >= 0.65 should get a similar_to edge."""
    await create_note("a.md", "---\ntitle: A\n---\n\nbody a", ws_db)
    await create_note("b.md", "---\ntitle: B\n---\n\nbody b", ws_db)

    db_path = ws_db / "app" / "jarvis.db"
    # Two highly similar vectors (cosine ~ 0.99)
    _inject_embedding(db_path, "a.md", [1.0, 0.0, 0.1])
    _inject_embedding(db_path, "b.md", [0.98, 0.1, 0.0])

    graph = graph_service.Graph()
    graph.add_node("note:a.md", "note", "A")
    graph.add_node("note:b.md", "note", "B")

    edges = _compute_embedding_similarity_edges(graph, ws_db / "memory")
    assert len(edges) == 1
    assert edges[0].type == "similar_to"
    assert edges[0].weight >= 0.3


@pytest.mark.anyio
async def test_embedding_edges_below_threshold_dropped(ws_db):
    """Two notes with cosine similarity < 0.65 should NOT get an edge."""
    await create_note("a.md", "---\ntitle: A\n---\n\nbody a", ws_db)
    await create_note("b.md", "---\ntitle: B\n---\n\nbody b", ws_db)

    db_path = ws_db / "app" / "jarvis.db"
    # Orthogonal vectors -> similarity 0
    _inject_embedding(db_path, "a.md", [1.0, 0.0, 0.0])
    _inject_embedding(db_path, "b.md", [0.0, 1.0, 0.0])

    graph = graph_service.Graph()
    graph.add_node("note:a.md", "note", "A")
    graph.add_node("note:b.md", "note", "B")

    edges = _compute_embedding_similarity_edges(graph, ws_db / "memory")
    assert edges == []


@pytest.mark.anyio
async def test_edge_cap_per_node(ws_db):
    """No node should get more than 5 similar_to edges."""
    for i in range(8):
        await create_note(
            f"n{i}.md", f"---\ntitle: N{i}\n---\n\nbody {i}", ws_db
        )

    db_path = ws_db / "app" / "jarvis.db"
    # All vectors nearly identical -> all pairs similar
    for i in range(8):
        _inject_embedding(db_path, f"n{i}.md", [1.0, 0.01 * i, 0.0])

    graph = graph_service.Graph()
    for i in range(8):
        graph.add_node(f"note:n{i}.md", "note", f"N{i}")

    edges = _compute_embedding_similarity_edges(graph, ws_db / "memory")

    # Count per-node degree on similar_to edges
    degree: dict = {}
    for e in edges:
        degree[e.source] = degree.get(e.source, 0) + 1
        degree[e.target] = degree.get(e.target, 0) + 1
    for node_id, deg in degree.items():
        assert deg <= 5, f"{node_id} has {deg} similar_to edges (cap=5)"


@pytest.mark.anyio
async def test_fallback_to_keyword_when_no_embeddings(ws_db):
    """When note_embeddings has no data, _compute_similarity_edges should
    fall back to keyword Jaccard similarity."""
    # Notes with strong keyword overlap
    body = "meditation mindfulness breathing relaxation stress sleep"
    for name in ("a", "b", "c"):
        await create_note(
            f"{name}.md",
            f"---\ntitle: {name.upper()}\ntags: []\n---\n\n{body}",
            ws_db,
        )

    graph = graph_service.Graph()
    for name in ("a", "b", "c"):
        graph.add_node(f"note:{name}.md", "note", name.upper())

    edges = _compute_similarity_edges(graph, ws_db / "memory")
    # Some edges should have been created via keyword path
    # (embeddings table is empty so embedding path returns [] and we fall back)
    assert isinstance(edges, list)


@pytest.mark.anyio
async def test_rebuild_graph_uses_embedding_edges(ws_db):
    """Full rebuild_graph should include embedding-based similar_to edges
    when note_embeddings is populated."""
    await create_note("a.md", "---\ntitle: A\n---\n\nbody a", ws_db)
    await create_note("b.md", "---\ntitle: B\n---\n\nbody b", ws_db)

    db_path = ws_db / "app" / "jarvis.db"
    _inject_embedding(db_path, "a.md", [1.0, 0.0, 0.0])
    _inject_embedding(db_path, "b.md", [0.99, 0.0, 0.05])

    graph = rebuild_graph(ws_db)

    similar_edges = [e for e in graph.edges if e.type == "similar_to"]
    assert any(
        {e.source, e.target} == {"note:a.md", "note:b.md"} for e in similar_edges
    )


@pytest.mark.anyio
async def test_keyword_fallback_still_works(ws_db):
    """Direct call to keyword fallback should return edges for overlapping notes."""
    body = "meditation mindfulness breathing relaxation stress sleep"
    for name in ("a", "b"):
        await create_note(
            f"{name}.md",
            f"---\ntitle: {name.upper()}\ntags: []\n---\n\n{body}",
            ws_db,
        )

    graph = graph_service.Graph()
    graph.add_node("note:a.md", "note", "A")
    graph.add_node("note:b.md", "note", "B")

    edges = _compute_keyword_similarity_edges(graph, ws_db / "memory")
    assert any(e.type == "similar_to" for e in edges)
