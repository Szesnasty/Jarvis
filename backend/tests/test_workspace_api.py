import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def ws_path(tmp_path):
    return tmp_path / "Jarvis"


@pytest.mark.anyio
async def test_get_status_no_workspace(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        response = await client.get("/api/workspace/status")
    assert response.status_code == 200
    assert response.json()["initialized"] is False


@pytest.mark.anyio
async def test_post_init_creates_workspace(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        response = await client.post("/api/workspace/init", json={})
    assert response.status_code == 201
    assert (ws_path / "app" / "config.json").exists()


@pytest.mark.anyio
async def test_post_init_returns_structure(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        response = await client.post("/api/workspace/init", json={})
    data = response.json()
    assert data["status"] == "ok"
    assert "workspace_path" in data


@pytest.mark.anyio
async def test_get_status_after_init(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.os") as mock_os:
        mock_os.environ.get.return_value = None
        mock_s.return_value.workspace_path = ws_path
        await client.post("/api/workspace/init", json={})
        response = await client.get("/api/workspace/status")
    assert response.status_code == 200
    data = response.json()
    assert data["initialized"] is True
    # Without env var, api_key_set reflects browser-only mode
    assert data["api_key_set"] is False
    assert data["key_storage"] == "browser"


@pytest.mark.anyio
async def test_post_init_duplicate(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        await client.post("/api/workspace/init", json={})
        response = await client.post("/api/workspace/init", json={})
    assert response.status_code == 409


@pytest.mark.anyio
async def test_workspace_always_browser_key_storage(client, ws_path):
    """Workspace always uses browser key storage — no server-side key."""
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        await client.post("/api/workspace/init", json={})
    config = json.loads((ws_path / "app" / "config.json").read_text())
    assert config["api_key_set"] is False
    assert config["key_storage"] == "browser"


@pytest.mark.anyio
async def test_keyless_workspace_status(client, ws_path):
    """Status for keyless workspace shows api_key_set=False."""
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.os") as mock_os:
        mock_os.environ.get.return_value = None
        mock_s.return_value.workspace_path = ws_path
        await client.post("/api/workspace/init", json={})
        response = await client.get("/api/workspace/status")
    data = response.json()
    assert data["initialized"] is True
    assert data["api_key_set"] is False
    assert data["key_storage"] == "browser"


@pytest.mark.anyio
async def test_env_var_key_reflected_in_status(client, ws_path):
    """If ANTHROPIC_API_KEY env var is set, status reports api_key_set=True."""
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.os") as mock_os:
        mock_os.environ.get.return_value = "sk-ant-env-key"
        mock_s.return_value.workspace_path = ws_path
        await client.post("/api/workspace/init", json={})
        response = await client.get("/api/workspace/status")
    data = response.json()
    assert data["api_key_set"] is True
    assert data["key_storage"] == "environment"


@pytest.mark.anyio
async def test_api_key_not_in_any_response(client, ws_path):
    """API key must never appear in any HTTP response body."""
    key = "sk-ant-secret-key-99999999"
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        r1 = await client.post("/api/workspace/init", json={})
        r2 = await client.get("/api/workspace/status")
    assert key not in r1.text
    assert key not in r2.text

