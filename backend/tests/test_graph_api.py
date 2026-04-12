from unittest.mock import patch

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from main import app
from models.database import init_database
from services.graph_service import invalidate_cache
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
async def ws_ready(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


@pytest.fixture
def patch_settings(ws_ready):
    with patch("services.memory_service.get_settings") as m1, \
         patch("services.graph_service.get_settings") as m2:
        for m in [m1, m2]:
            m.return_value.workspace_path = ws_ready
        yield ws_ready


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


NOTE_A = "---\ntitle: Note A\ntags: [python]\n---\n\nPython content."


@pytest.mark.anyio
async def test_post_rebuild_200(client, patch_settings):
    await create_note("inbox/note-a.md", NOTE_A, patch_settings)
    r = await client.post("/api/graph/rebuild")
    assert r.status_code == 200
    data = r.json()
    assert "node_count" in data
    assert data["node_count"] >= 1


@pytest.mark.anyio
async def test_get_graph_200(client, patch_settings):
    await create_note("inbox/note-a.md", NOTE_A, patch_settings)
    await client.post("/api/graph/rebuild")
    r = await client.get("/api/graph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data


@pytest.mark.anyio
async def test_get_graph_empty(client, patch_settings):
    r = await client.get("/api/graph")
    assert r.status_code == 200
    data = r.json()
    assert data["nodes"] == []


@pytest.mark.anyio
async def test_get_graph_neighbors_200(client, patch_settings):
    await create_note("inbox/note-a.md", NOTE_A, patch_settings)
    await client.post("/api/graph/rebuild")
    r = await client.get("/api/graph/neighbors", params={"node_id": "note:inbox/note-a.md"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.anyio
async def test_get_graph_neighbors_unknown(client, patch_settings):
    await client.post("/api/graph/rebuild")
    r = await client.get("/api/graph/neighbors", params={"node_id": "note:nonexistent.md"})
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.anyio
async def test_get_graph_stats(client, patch_settings):
    await create_note("inbox/note-a.md", NOTE_A, patch_settings)
    await client.post("/api/graph/rebuild")
    r = await client.get("/api/graph/stats")
    assert r.status_code == 200
    data = r.json()
    assert "node_count" in data
    assert "edge_count" in data


@pytest.mark.anyio
async def test_graph_not_built_yet(client, patch_settings):
    r = await client.get("/api/graph")
    assert r.status_code == 200
    assert r.json()["nodes"] == []


@pytest.mark.anyio
async def test_rebuild_after_note_change(client, patch_settings):
    await create_note("inbox/note-a.md", NOTE_A, patch_settings)
    await client.post("/api/graph/rebuild")
    r1 = await client.get("/api/graph/stats")
    count1 = r1.json()["node_count"]

    await create_note("inbox/note-b.md", "---\ntitle: Note B\ntags: [ai]\n---\n\nAI content.", patch_settings)
    invalidate_cache()
    await client.post("/api/graph/rebuild")
    r2 = await client.get("/api/graph/stats")
    count2 = r2.json()["node_count"]
    assert count2 > count1
