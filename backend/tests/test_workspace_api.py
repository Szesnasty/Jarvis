import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def ws_path(tmp_path):
    return tmp_path / "Jarvis"


@pytest.fixture
def mock_settings(ws_path):
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        with patch("routers.workspace.get_workspace_status", wraps=None) as _:
            yield mock_s


@pytest.mark.anyio
async def test_get_status_no_workspace(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s:
        mock_s.return_value.workspace_path = ws_path
        response = await client.get("/api/workspace/status")
    assert response.status_code == 200
    assert response.json()["initialized"] is False


@pytest.mark.anyio
async def test_post_init_creates_workspace(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.keyring"):
        mock_s.return_value.workspace_path = ws_path
        response = await client.post(
            "/api/workspace/init",
            json={"api_key": "sk-ant-test-key-12345678901234"},
        )
    assert response.status_code == 201
    assert (ws_path / "app" / "config.json").exists()


@pytest.mark.anyio
async def test_post_init_returns_structure(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.keyring"):
        mock_s.return_value.workspace_path = ws_path
        response = await client.post(
            "/api/workspace/init",
            json={"api_key": "sk-ant-test-key-12345678901234"},
        )
    data = response.json()
    assert data["status"] == "ok"
    assert "workspace_path" in data


@pytest.mark.anyio
async def test_get_status_after_init(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.keyring"):
        mock_s.return_value.workspace_path = ws_path
        await client.post(
            "/api/workspace/init",
            json={"api_key": "sk-ant-test-key-12345678901234"},
        )
        response = await client.get("/api/workspace/status")
    assert response.status_code == 200
    data = response.json()
    assert data["initialized"] is True
    assert data["api_key_set"] is True


@pytest.mark.anyio
async def test_post_init_duplicate(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.keyring"):
        mock_s.return_value.workspace_path = ws_path
        await client.post(
            "/api/workspace/init",
            json={"api_key": "sk-ant-test-key-12345678901234"},
        )
        response = await client.post(
            "/api/workspace/init",
            json={"api_key": "sk-ant-test-key-12345678901234"},
        )
    assert response.status_code == 409


@pytest.mark.anyio
async def test_post_init_missing_api_key(client):
    response = await client.post("/api/workspace/init", json={})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_init_empty_api_key(client, ws_path):
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.keyring"):
        mock_s.return_value.workspace_path = ws_path
        response = await client.post(
            "/api/workspace/init",
            json={"api_key": ""},
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_api_key_not_in_any_response(client, ws_path):
    key = "sk-ant-secret-key-99999999"
    with patch("services.workspace_service.get_settings") as mock_s, \
         patch("services.workspace_service.keyring"):
        mock_s.return_value.workspace_path = ws_path
        r1 = await client.post("/api/workspace/init", json={"api_key": key})
        r2 = await client.get("/api/workspace/status")
    assert key not in r1.text
    assert key not in r2.text
