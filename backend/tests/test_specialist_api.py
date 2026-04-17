import json

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


SAMPLE_DATA = {
    "name": "Health Guide",
    "role": "Health assistant",
    "sources": ["memory/knowledge/health/"],
    "rules": ["Never diagnose"],
    "tools": ["search_notes", "read_note"],
    "icon": "🏥",
}


@pytest.fixture
def patch_settings(tmp_path, monkeypatch):
    """Patch get_settings so specialist_service uses tmp_path as workspace."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.workspace_path = tmp_path
    monkeypatch.setattr("services.specialist_service.get_settings", lambda: settings)
    (tmp_path / "agents").mkdir(exist_ok=True)
    (tmp_path / ".trash").mkdir(exist_ok=True)
    return tmp_path


@pytest.mark.anyio
async def test_post_specialist_201(client, patch_settings):
    resp = await client.post("/api/specialists", json=SAMPLE_DATA)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "health-guide"
    assert data["name"] == "Health Guide"


@pytest.mark.anyio
async def test_post_specialist_invalid(client, patch_settings):
    resp = await client.post("/api/specialists", json={"name": ""})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_get_specialists_200(client, patch_settings):
    await client.post("/api/specialists", json=SAMPLE_DATA)
    resp = await client.get("/api/specialists")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Health Guide"


@pytest.mark.anyio
async def test_get_specialist_by_id_200(client, patch_settings):
    await client.post("/api/specialists", json=SAMPLE_DATA)
    resp = await client.get("/api/specialists/health-guide")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Health Guide"


@pytest.mark.anyio
async def test_get_specialist_404(client, patch_settings):
    resp = await client.get("/api/specialists/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_put_specialist_200(client, patch_settings):
    await client.post("/api/specialists", json=SAMPLE_DATA)
    resp = await client.put("/api/specialists/health-guide", json={"role": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "Updated"


@pytest.mark.anyio
async def test_delete_specialist_200(client, patch_settings):
    await client.post("/api/specialists", json=SAMPLE_DATA)
    resp = await client.delete("/api/specialists/health-guide")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


@pytest.mark.anyio
async def test_post_activate_200(client, patch_settings):
    await client.post("/api/specialists", json=SAMPLE_DATA)
    resp = await client.post("/api/specialists/activate/health-guide")
    assert resp.status_code == 200
    assert resp.json()["status"] == "activated"


@pytest.mark.anyio
async def test_post_deactivate_200(client, patch_settings):
    resp = await client.post("/api/specialists/deactivate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deactivated"


@pytest.mark.anyio
async def test_get_active_specialist(client, patch_settings):
    resp = await client.get("/api/specialists/active")
    assert resp.status_code == 200
    assert resp.json() == []

    await client.post("/api/specialists", json=SAMPLE_DATA)
    await client.post("/api/specialists/activate/health-guide")
    resp = await client.get("/api/specialists/active")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "health-guide"
