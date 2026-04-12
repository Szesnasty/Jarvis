"""Full regression smoke tests — verify all major features still work together."""

import json

import pytest

from services.specialist_service import reset_state

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def patch_all(tmp_path, monkeypatch):
    """Patch settings across all services for integration tests."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.workspace_path = tmp_path

    for mod in [
        "services.workspace_service",
        "services.memory_service",
        "services.preference_service",
        "services.token_tracking",
        "services.specialist_service",
        "services.graph_service",
        "services.session_service",
        "routers.settings",
    ]:
        try:
            monkeypatch.setattr(f"{mod}.get_settings", lambda: settings)
        except AttributeError:
            pass

    # Create workspace structure
    for d in ["app", "app/logs", "app/sessions", "memory", "memory/inbox",
              "memory/knowledge", "memory/daily", "agents", ".trash", "graph"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    config = {"version": "0.1.0", "api_key_set": True, "workspace_path": str(tmp_path)}
    (tmp_path / "app" / "config.json").write_text(json.dumps(config))
    key_file = tmp_path / "app" / "api_key.json"
    key_file.write_text(json.dumps({"api_key": "sk-test-smoke"}))

    return tmp_path


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


@pytest.mark.anyio
async def test_health_still_works(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.anyio
async def test_workspace_status(client, patch_all):
    resp = await client.get("/api/workspace/status")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_create_and_search_note(client, patch_all):
    from models.database import init_database
    await init_database(patch_all / "app" / "jarvis.db")

    content = "---\ntitle: Smoke Test\ntags: [smoke]\n---\n\nSmoke test content."
    resp = await client.post("/api/memory/notes/inbox/smoke.md", json={"content": content})
    assert resp.status_code == 201

    resp = await client.get("/api/memory/notes", params={"search": "smoke"})
    assert resp.status_code == 200
    results = resp.json()
    assert any(n["title"] == "Smoke Test" for n in results)


@pytest.mark.anyio
async def test_graph_rebuild_after_note(client, patch_all):
    from models.database import init_database
    await init_database(patch_all / "app" / "jarvis.db")

    content = "---\ntitle: Graph Note\ntags: [graph]\n---\n\nLink to [[Other Note]]."
    (patch_all / "memory" / "inbox" / "graph.md").write_text(content)

    resp = await client.post("/api/graph/rebuild")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_session_save_and_load(client, patch_all):
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_specialist_crud(client, patch_all):
    # Create
    data = {"name": "Test Specialist", "role": "Testing"}
    resp = await client.post("/api/specialists", json=data)
    assert resp.status_code == 200
    spec_id = resp.json()["id"]

    # Get
    resp = await client.get(f"/api/specialists/{spec_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Specialist"

    # Edit
    resp = await client.put(f"/api/specialists/{spec_id}", json={"role": "Updated"})
    assert resp.status_code == 200

    # Delete
    resp = await client.delete(f"/api/specialists/{spec_id}")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_preferences_round_trip(client, patch_all):
    resp = await client.patch("/api/preferences", json={"key": "theme", "value": "dark"})
    assert resp.status_code == 200

    resp = await client.get("/api/preferences")
    assert resp.status_code == 200
    assert resp.json().get("theme") == "dark"


@pytest.mark.anyio
async def test_settings_update(client, patch_all):
    resp = await client.patch("/api/settings/voice", json={"auto_speak": "true"})
    assert resp.status_code == 200

    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.json()["voice"]["auto_speak"] == "true"


@pytest.mark.anyio
async def test_import_and_find(client, patch_all):
    from models.database import init_database
    await init_database(patch_all / "app" / "jarvis.db")

    # Create a temp file to import
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        f.write("---\ntitle: Imported\ntags: [import]\n---\n\nImported content.")
        f.flush()

        from services.ingest import fast_ingest
        from pathlib import Path
        result = await fast_ingest(Path(f.name), "knowledge", workspace_path=patch_all)
        assert result["folder"] == "knowledge"


@pytest.mark.anyio
async def test_no_api_key_leak_anywhere(client, patch_all):
    """Scan key endpoints to ensure no raw API key appears."""
    endpoints = [
        ("/api/health", "GET"),
        ("/api/workspace/status", "GET"),
        ("/api/settings", "GET"),
        ("/api/specialists", "GET"),
        ("/api/preferences", "GET"),
    ]
    for url, method in endpoints:
        if method == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url)
        raw = resp.text
        assert "sk-test-smoke" not in raw, f"API key leaked in {url}"
