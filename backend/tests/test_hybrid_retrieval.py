"""Tests for the hybrid retrieval pipeline (BM25 + cosine + graph fusion)."""
import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services import embedding_service, retrieval
from services.graph_service import invalidate_cache, rebuild_graph
from services.memory_service import create_note
from services.retrieval import retrieve


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


@pytest.fixture
def fake_cosine(monkeypatch):
    """Bypass the real embedding model: return canned cosine scores per path.

    Tests can mutate ``scores`` to simulate different semantic matches.
    """
    scores: dict = {}

    async def fake_search_similar(query, limit=10, workspace_path=None):
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:limit]

    async def fake_embed_note(*args, **kwargs):
        return False

    # Keep the disable env var so create_note skips the real embedder,
    # but patch the retrieval-side calls to behave as if cosine is live.
    monkeypatch.setattr(embedding_service, "is_available", lambda: True)
    monkeypatch.setattr(embedding_service, "search_similar", fake_search_similar)
    monkeypatch.setattr(embedding_service, "embed_note", fake_embed_note)
    # retrieval.py guards on JARVIS_DISABLE_EMBEDDINGS; clear it for this test
    # scope so the cosine branch runs against our stubs.
    monkeypatch.delenv("JARVIS_DISABLE_EMBEDDINGS", raising=False)
    return scores


@pytest.mark.anyio
async def test_cosine_adds_non_keyword_results(ws_db, fake_cosine):
    """A note matched only by cosine (not BM25) should still appear in results."""
    await create_note(
        "inbox/keyword.md",
        "---\ntitle: Productivity\ntags: []\n---\n\nProductivity tips for work.",
        ws_db,
    )
    await create_note(
        "inbox/semantic.md",
        "---\ntitle: Deep Work\ntags: []\n---\n\nFlow state and concentration.",
        ws_db,
    )

    # BM25 only matches 'productivity'. Cosine pretends semantic.md is close too.
    fake_cosine["inbox/semantic.md"] = 0.9

    results = await retrieve("productivity", limit=5, workspace_path=ws_db)
    paths = [r["path"] for r in results]
    assert "inbox/keyword.md" in paths
    assert "inbox/semantic.md" in paths


@pytest.mark.anyio
async def test_signals_metadata_in_results(ws_db, fake_cosine):
    """Every result must expose a ``_signals`` dict with three normalized scores."""
    await create_note(
        "inbox/alpha.md",
        "---\ntitle: Alpha\ntags: []\n---\n\nAlpha content.",
        ws_db,
    )
    fake_cosine["inbox/alpha.md"] = 0.8

    results = await retrieve("alpha", limit=5, workspace_path=ws_db)
    assert len(results) == 1
    signals = results[0]["_signals"]
    assert set(signals.keys()) == {"bm25", "cosine", "graph"}
    assert 0.0 <= signals["bm25"] <= 1.0
    assert 0.0 <= signals["cosine"] <= 1.0
    assert 0.0 <= signals["graph"] <= 1.0


@pytest.mark.anyio
async def test_weights_normalize_when_cosine_unavailable(ws_db, monkeypatch):
    """Without cosine, retrieval should still return BM25 candidates ranked
    by the renormalized BM25+graph weights."""
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")
    monkeypatch.setattr(embedding_service, "is_available", lambda: False)

    await create_note(
        "inbox/alpha.md",
        "---\ntitle: Alpha\ntags: []\n---\n\nAlpha content about productivity.",
        ws_db,
    )

    results = await retrieve("productivity", limit=5, workspace_path=ws_db)
    assert len(results) >= 1
    # All signals still reported (cosine will be 0)
    assert results[0]["_signals"]["cosine"] == 0.0
    assert results[0]["_signals"]["bm25"] > 0


@pytest.mark.anyio
async def test_empty_query_returns_empty(ws_db, fake_cosine):
    assert await retrieve("", workspace_path=ws_db) == []
    assert await retrieve("   ", workspace_path=ws_db) == []


@pytest.mark.anyio
async def test_graph_boost_from_similar_to_cluster(ws_db, fake_cosine):
    """A note connected to other candidates via similar_to edges should
    receive a cluster bonus in its graph signal."""
    await create_note(
        "inbox/center.md",
        "---\ntitle: Center Topic\ntags: [topic]\n---\n\nMain topic content.",
        ws_db,
    )
    await create_note(
        "inbox/leaf1.md",
        "---\ntitle: Leaf One\ntags: [topic]\n---\n\nLeaf one about topic.",
        ws_db,
    )
    await create_note(
        "inbox/leaf2.md",
        "---\ntitle: Leaf Two\ntags: [topic]\n---\n\nLeaf two about topic.",
        ws_db,
    )

    # All three should appear via BM25 ("topic") and cosine.
    fake_cosine["inbox/center.md"] = 0.9
    fake_cosine["inbox/leaf1.md"] = 0.85
    fake_cosine["inbox/leaf2.md"] = 0.85

    # Manually inject similar_to edges via a fake graph
    from services import graph_service
    from services.graph_service import builder as _graph_builder
    graph = graph_service.Graph()
    graph.add_node("note:inbox/center.md", "note", "Center Topic", folder="inbox")
    graph.add_node("note:inbox/leaf1.md", "note", "Leaf One", folder="inbox")
    graph.add_node("note:inbox/leaf2.md", "note", "Leaf Two", folder="inbox")
    graph.add_edge("note:inbox/center.md", "note:inbox/leaf1.md", "similar_to", weight=0.9)
    graph.add_edge("note:inbox/center.md", "note:inbox/leaf2.md", "similar_to", weight=0.9)
    _graph_builder._graph_cache = graph

    results = await retrieve("topic", limit=5, workspace_path=ws_db)
    assert len(results) >= 1
    center = next((r for r in results if r["path"] == "inbox/center.md"), None)
    assert center is not None
    # Center note should have graph signal > 0 (edges + cluster bonus)
    assert center["_signals"]["graph"] > 0


@pytest.mark.anyio
async def test_cluster_dedup_limits_per_folder(ws_db, fake_cosine):
    """At most 2 results per folder should be returned."""
    for i in range(5):
        await create_note(
            f"inbox/note-{i}.md",
            f"---\ntitle: Note {i}\ntags: [test]\n---\n\nContent {i}.",
            ws_db,
        )

    results = await retrieve("test", limit=10, workspace_path=ws_db)
    folders = [r.get("folder", "") for r in results]
    assert folders.count("inbox") <= 2
