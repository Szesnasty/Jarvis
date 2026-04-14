import json
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from main import app
from models.database import init_database
from services.session_service import (
    _sessions,
    add_message,
    create_session,
    save_session,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory" / "plans").mkdir(parents=True)
    (tmp_path / "app" / "sessions").mkdir(parents=True)
    return tmp_path


@pytest.fixture
async def ws_ready(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


@pytest.fixture(autouse=True)
def clean_sessions():
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture
def patch_settings(ws_ready):
    with patch("services.memory_service.get_settings") as m1, \
         patch("services.planning_service.get_settings") as m2, \
         patch("services.session_service.get_settings") as m3, \
         patch("services.preference_service.get_settings") as m4:
        for m in [m1, m2, m3, m4]:
            m.return_value.workspace_path = ws_ready
        yield ws_ready


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_get_sessions_200(client, patch_settings):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi there")
    save_session(sid, patch_settings)

    r = await client.get("/api/sessions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.anyio
async def test_get_session_by_id_200(client, patch_settings):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi there")
    save_session(sid, patch_settings)

    r = await client.get(f"/api/sessions/{sid}")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sid
    assert len(data["messages"]) == 2


@pytest.mark.anyio
async def test_get_session_404(client, patch_settings):
    r = await client.get("/api/sessions/nonexistent")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_preferences_200(client, patch_settings):
    r = await client.get("/api/preferences")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


@pytest.mark.anyio
async def test_set_preference_200(client, patch_settings):
    r = await client.patch("/api/preferences", json={"key": "style", "value": "concise"})
    assert r.status_code == 200
    data = r.json()
    assert data["style"] == "concise"


@pytest.mark.anyio
async def test_resume_session_200(client, patch_settings):
    sid = create_session()
    add_message(sid, "user", "Old conversation")
    add_message(sid, "assistant", "Old reply")
    save_session(sid, patch_settings)
    _sessions.clear()

    r = await client.post(f"/api/sessions/{sid}/resume")
    assert r.status_code == 200
    assert r.json()["status"] == "resumed"
