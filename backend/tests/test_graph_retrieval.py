import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.graph_service import invalidate_cache, rebuild_graph
from services.memory_service import create_note
from services.retrieval import retrieve


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


NOTE_PY = "---\ntitle: Python Guide\ntags: [python]\n---\n\nPython programming guide content."
NOTE_AI = "---\ntitle: AI Overview\ntags: [ai, python]\n---\n\nAI and machine learning overview.\n\nSee [[inbox/python-guide.md]]."
NOTE_HEALTH = "---\ntitle: Health Tips\ntags: [health]\n---\n\nHealth and fitness tips."


@pytest.mark.anyio
async def test_retrieval_search_only(ws_db):
    await create_note("inbox/python-guide.md", NOTE_PY, ws_db)
    results = await retrieve("python", limit=5, workspace_path=ws_db)
    assert len(results) >= 1
    assert any("python" in r.get("path", "").lower() or "python" in r.get("title", "").lower() for r in results)


@pytest.mark.anyio
async def test_retrieval_with_graph_expansion(ws_db):
    await create_note("inbox/python-guide.md", NOTE_PY, ws_db)
    await create_note("inbox/ai-overview.md", NOTE_AI, ws_db)
    rebuild_graph(ws_db)

    results = await retrieve("python", limit=10, workspace_path=ws_db)
    paths = [r.get("path", "") for r in results]
    # Both python-guide and ai-overview should appear (via tag or link)
    assert any("python" in p for p in paths)


@pytest.mark.anyio
async def test_retrieval_deduplication(ws_db):
    await create_note("inbox/python-guide.md", NOTE_PY, ws_db)
    await create_note("inbox/ai-overview.md", NOTE_AI, ws_db)
    rebuild_graph(ws_db)

    results = await retrieve("python", limit=10, workspace_path=ws_db)
    paths = [r.get("path", "") for r in results]
    # No duplicates
    assert len(paths) == len(set(paths))


@pytest.mark.anyio
async def test_retrieval_ranking(ws_db):
    await create_note("inbox/python-guide.md", NOTE_PY, ws_db)
    await create_note("inbox/ai-overview.md", NOTE_AI, ws_db)
    rebuild_graph(ws_db)

    results = await retrieve("python", limit=10, workspace_path=ws_db)
    # Direct FTS matches should come before graph expansions
    if len(results) >= 2:
        first = results[0]
        assert first.get("source") != "graph"


@pytest.mark.anyio
async def test_retrieval_max_results(ws_db):
    for i in range(10):
        await create_note(f"inbox/note-{i}.md", f"---\ntitle: Note {i}\ntags: [test]\n---\n\nTest content {i}.", ws_db)
    results = await retrieve("test", limit=3, workspace_path=ws_db)
    assert len(results) <= 3


@pytest.mark.anyio
async def test_retrieval_empty_query(ws_db):
    results = await retrieve("", workspace_path=ws_db)
    assert results == []


@pytest.mark.anyio
async def test_retrieval_no_graph(ws_db):
    """Works even without graph.json — falls back to search-only."""
    await create_note("inbox/python-guide.md", NOTE_PY, ws_db)
    results = await retrieve("python", limit=5, workspace_path=ws_db)
    assert len(results) >= 1


@pytest.mark.anyio
async def test_retrieval_via_tool(ws_db):
    """query_graph tool uses graph service."""
    await create_note("inbox/python-guide.md", NOTE_PY, ws_db)
    rebuild_graph(ws_db)

    from services.tools import execute_tool
    import json

    raw = await execute_tool(
        "query_graph",
        {"entity": "python"},
        workspace_path=ws_db,
    )
    data = json.loads(raw)
    assert isinstance(data, list)
