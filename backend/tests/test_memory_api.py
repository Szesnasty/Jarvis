from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_ready(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


@pytest.fixture
def patch_settings(ws_ready):
    with patch("services.memory_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_ready
        yield ws_ready


SAMPLE = "---\ntitle: API Test\ntags: [test]\n---\n\nAPI test note content."




@pytest.mark.anyio
async def test_post_notes_201(client, patch_settings):
    r = await client.post("/api/memory/notes/inbox/test.md", json={"content": SAMPLE})
    assert r.status_code == 201
    assert r.json()["path"] == "inbox/test.md"




@pytest.mark.anyio
async def test_post_notes_invalid_body(client):
    r = await client.post("/api/memory/notes/inbox/test.md", json={})
    assert r.status_code == 422




@pytest.mark.anyio
async def test_get_notes_list_200(client, patch_settings):
    await client.post("/api/memory/notes/inbox/a.md", json={"content": SAMPLE})
    r = await client.get("/api/memory/notes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == 1




@pytest.mark.anyio
async def test_get_notes_list_empty(client, patch_settings):
    r = await client.get("/api/memory/notes")
    assert r.status_code == 200
    assert r.json() == []




@pytest.mark.anyio
async def test_get_notes_search_200(client, patch_settings):
    await client.post("/api/memory/notes/inbox/py.md", json={"content": "---\ntitle: Py\n---\n\npython rocks"})
    r = await client.get("/api/memory/notes", params={"search": "python"})
    assert r.status_code == 200
    assert len(r.json()) >= 1




@pytest.mark.anyio
async def test_get_note_by_path_200(client, patch_settings):
    await client.post("/api/memory/notes/inbox/test.md", json={"content": SAMPLE})
    r = await client.get("/api/memory/notes/inbox/test.md")
    assert r.status_code == 200
    assert "API test note" in r.json()["content"]




@pytest.mark.anyio
async def test_get_note_by_path_404(client, patch_settings):
    r = await client.get("/api/memory/notes/inbox/nope.md")
    assert r.status_code == 404




@pytest.mark.anyio
async def test_delete_note_200(client, patch_settings):
    await client.post("/api/memory/notes/inbox/test.md", json={"content": SAMPLE})
    r = await client.delete("/api/memory/notes/inbox/test.md")
    assert r.status_code == 200




@pytest.mark.anyio
async def test_delete_note_404(client, patch_settings):
    r = await client.delete("/api/memory/notes/inbox/nope.md")
    assert r.status_code == 404




@pytest.mark.anyio
async def test_post_reindex_200(client, patch_settings):
    r = await client.post("/api/memory/reindex")
    assert r.status_code == 200
    assert "indexed" in r.json()




@pytest.mark.anyio
async def test_path_traversal_blocked(client, patch_settings):
    r = await client.post("/api/memory/notes/inbox/..%2F..%2Fetc%2Fpasswd", json={"content": "hack"})
    assert r.status_code == 400


@pytest.mark.anyio
async def test_post_ingest_url_200(client, patch_settings, monkeypatch):
    async def _fake_ingest_url(url: str, folder: str = "knowledge", summarize: bool = False, api_key=None):
        return {
            "path": f"{folder}/yt-dQw4w9WgXcQ.md",
            "title": "YouTube: dQw4w9WgXcQ",
            "type": "youtube",
            "source": url,
            "word_count": 123,
        }

    monkeypatch.setattr("services.url_ingest.ingest_url", _fake_ingest_url)

    r = await client.post(
        "/api/memory/ingest-url",
        json={"url": "https://youtu.be/dQw4w9WgXcQ", "folder": "knowledge", "summarize": False},
    )
    assert r.status_code == 200
    assert r.json()["type"] == "youtube"


@pytest.mark.anyio
async def test_post_ingest_url_400(client, patch_settings, monkeypatch):
    from services.ingest import IngestError

    async def _fake_ingest_url(url: str, folder: str = "knowledge", summarize: bool = False, api_key=None):
        raise IngestError("boom")

    monkeypatch.setattr("services.url_ingest.ingest_url", _fake_ingest_url)

    r = await client.post(
        "/api/memory/ingest-url",
        json={"url": "https://example.com", "folder": "knowledge", "summarize": False},
    )
    assert r.status_code == 400
