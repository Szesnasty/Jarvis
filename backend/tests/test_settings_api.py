import json

import pytest

from services.specialist_service import reset_state

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def patch_settings(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.workspace_path = tmp_path
    monkeypatch.setattr("services.workspace_service.get_settings", lambda: settings)
    monkeypatch.setattr("services.preference_service.get_settings", lambda: settings)
    monkeypatch.setattr("services.token_tracking.get_settings", lambda: settings)
    monkeypatch.setattr("routers.settings.get_settings", lambda: settings)
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "logs").mkdir(exist_ok=True)
    config = {"version": "0.1.0", "api_key_set": True, "workspace_path": str(tmp_path)}
    (tmp_path / "app" / "config.json").write_text(json.dumps(config))
    # Store a fake key
    key_file = tmp_path / "app" / "api_key.json"
    key_file.write_text(json.dumps({"api_key": "sk-test-123"}))
    return tmp_path


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


@pytest.mark.anyio
async def test_get_settings_200(client, patch_settings):
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "workspace_path" in data
    assert "api_key_set" in data
    assert "voice" in data


@pytest.mark.anyio
async def test_get_settings_no_raw_key(client, patch_settings):
    resp = await client.get("/api/settings")
    data = resp.json()
    raw = json.dumps(data)
    assert "sk-test-123" not in raw


@pytest.mark.anyio
async def test_update_api_key(client, patch_settings):
    resp = await client.patch("/api/settings/api-key", json={"api_key": "sk-new-key"})
    assert resp.status_code == 200
    assert resp.json()["api_key_set"] is True


@pytest.mark.anyio
async def test_update_api_key_empty_rejected(client, patch_settings):
    resp = await client.patch("/api/settings/api-key", json={"api_key": ""})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_update_voice_prefs(client, patch_settings):
    resp = await client.patch("/api/settings/voice", json={"auto_speak": "true"})
    assert resp.status_code == 200
    assert resp.json()["auto_speak"] == "true"


@pytest.mark.anyio
async def test_update_voice_prefs_invalid(client, patch_settings):
    resp = await client.patch("/api/settings/voice", json={"invalid_key": "value"})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_get_settings_includes_voice_prefs(client, patch_settings):
    await client.patch("/api/settings/voice", json={"auto_speak": "true"})
    resp = await client.get("/api/settings")
    assert resp.json()["voice"]["auto_speak"] == "true"


@pytest.mark.anyio
async def test_settings_survives_restart(client, patch_settings):
    await client.patch("/api/settings/voice", json={"tts_voice": "alloy"})
    resp = await client.get("/api/settings")
    assert resp.json()["voice"]["tts_voice"] == "alloy"
