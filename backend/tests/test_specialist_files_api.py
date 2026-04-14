import io

import pytest

from services.specialist_service import reset_state

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


SAMPLE_DATA = {"name": "Health Guide", "role": "Health assistant", "icon": "\U0001f3e5"}


@pytest.fixture
def patch_settings(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.workspace_path = tmp_path
    monkeypatch.setattr("services.specialist_service.get_settings", lambda: settings)
    (tmp_path / "agents").mkdir(exist_ok=True)
    (tmp_path / ".trash").mkdir(exist_ok=True)
    return tmp_path


async def _create_specialist(client):
    resp = await client.post("/api/specialists", json=SAMPLE_DATA)
    assert resp.status_code == 200
    return resp.json()


# --- GET /api/specialists/{id}/files ---


@pytest.mark.anyio
async def test_list_files_empty(client, patch_settings):
    await _create_specialist(client)
    resp = await client.get("/api/specialists/health-guide/files")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_list_files_404(client, patch_settings):
    resp = await client.get("/api/specialists/nonexistent/files")
    assert resp.status_code == 404


# --- POST /api/specialists/{id}/files ---


@pytest.mark.anyio
async def test_upload_file(client, patch_settings):
    await _create_specialist(client)
    resp = await client.post(
        "/api/specialists/health-guide/files",
        files={"file": ("notes.md", b"# Hello\nWorld", "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "notes.md"
    assert data["size"] == 13


@pytest.mark.anyio
async def test_upload_file_invalid_extension(client, patch_settings):
    await _create_specialist(client)
    resp = await client.post(
        "/api/specialists/health-guide/files",
        files={"file": ("script.exe", b"bad", "application/octet-stream")},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_upload_file_404(client, patch_settings):
    resp = await client.post(
        "/api/specialists/nonexistent/files",
        files={"file": ("notes.md", b"data", "text/markdown")},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_upload_then_list(client, patch_settings):
    await _create_specialist(client)
    await client.post(
        "/api/specialists/health-guide/files",
        files={"file": ("a.md", b"aaa", "text/markdown")},
    )
    await client.post(
        "/api/specialists/health-guide/files",
        files={"file": ("b.txt", b"bbb", "text/plain")},
    )
    resp = await client.get("/api/specialists/health-guide/files")
    assert resp.status_code == 200
    filenames = [f["filename"] for f in resp.json()]
    assert "a.md" in filenames
    assert "b.txt" in filenames


# --- DELETE /api/specialists/{id}/files/{filename} ---


@pytest.mark.anyio
async def test_delete_file(client, patch_settings):
    await _create_specialist(client)
    await client.post(
        "/api/specialists/health-guide/files",
        files={"file": ("notes.md", b"data", "text/markdown")},
    )
    resp = await client.delete("/api/specialists/health-guide/files/notes.md")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify it's gone
    resp = await client.get("/api/specialists/health-guide/files")
    assert len(resp.json()) == 0


@pytest.mark.anyio
async def test_delete_file_not_found(client, patch_settings):
    await _create_specialist(client)
    resp = await client.delete("/api/specialists/health-guide/files/missing.md")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_file_path_traversal(client, patch_settings):
    await _create_specialist(client)
    # URL-decoded slashes won't match the route (no :path converter), so 404 or 422
    resp = await client.delete("/api/specialists/health-guide/files/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (404, 422)
    # Also test a traversal without slashes
    resp = await client.delete("/api/specialists/health-guide/files/..passwd")
    assert resp.status_code == 422


# --- file_count in list response ---


@pytest.mark.anyio
async def test_list_specialists_includes_file_count(client, patch_settings):
    await _create_specialist(client)
    await client.post(
        "/api/specialists/health-guide/files",
        files={"file": ("a.md", b"aaa", "text/markdown")},
    )
    resp = await client.get("/api/specialists")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["file_count"] == 1
