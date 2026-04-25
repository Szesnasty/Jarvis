"""Tests for step-26d retrieval settings toggles via GET/PATCH /api/settings/retrieval.

Tests:
- default config returns expected defaults
- use_suggested_strong=False → no suggested_related contribution
- use_part_of=False → part_of weight is 0.0
- use_related=False → related weight is 0.0
- PATCH /retrieval updates config.json; re-read returns new values
"""

from __future__ import annotations

import json
import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def patch_workspace(ws, monkeypatch):
    fake_settings = lambda: type("S", (), {"workspace_path": ws})()
    monkeypatch.setattr("config.get_settings", fake_settings)
    monkeypatch.setattr("routers.settings.get_settings", fake_settings)
    monkeypatch.setattr("services.entity_extraction.extract_entities", lambda *a, **k: [])
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")


# ---------------------------------------------------------------------------
# _load_graph_expansion_config
# ---------------------------------------------------------------------------

def test_default_config_no_file(ws):
    """When no config.json exists, defaults are returned."""
    from services.retrieval.pipeline import _load_graph_expansion_config
    cfg = _load_graph_expansion_config(ws)
    assert cfg["use_related"] is True
    assert cfg["use_part_of"] is True
    assert cfg["use_suggested_strong"] is False


def test_partial_override_in_config(ws):
    """A partial config.json merge leaves unset keys at their defaults."""
    from services.retrieval.pipeline import _load_graph_expansion_config
    config_path = ws / "app" / "config.json"
    config_path.write_text(
        json.dumps({"retrieval": {"graph_expansion": {"use_suggested_strong": True}}}),
        encoding="utf-8",
    )
    cfg = _load_graph_expansion_config(ws)
    assert cfg["use_suggested_strong"] is True
    assert cfg["use_related"] is True  # default retained
    assert cfg["use_part_of"] is True  # default retained


def test_invalid_config_returns_defaults(ws):
    """Corrupt config.json silently falls back to defaults."""
    from services.retrieval.pipeline import _load_graph_expansion_config
    (ws / "app" / "config.json").write_text("{not valid json}", encoding="utf-8")
    cfg = _load_graph_expansion_config(ws)
    assert cfg["use_related"] is True


# ---------------------------------------------------------------------------
# HTTP endpoints: GET/PATCH /api/settings/retrieval
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_retrieval_returns_defaults(ws):
    from httpx import ASGITransport, AsyncClient
    from main import app
    from models.database import init_database
    await init_database(ws / "app" / "jarvis.db")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/settings/retrieval")
    assert resp.status_code == 200
    ge = resp.json()["graph_expansion"]
    assert ge["use_related"] is True
    assert ge["use_part_of"] is True
    assert ge["use_suggested_strong"] is False


@pytest.mark.anyio
async def test_patch_retrieval_updates_config(ws):
    from httpx import ASGITransport, AsyncClient
    from main import app
    from models.database import init_database
    await init_database(ws / "app" / "jarvis.db")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/settings/retrieval",
            json={"graph_expansion": {"use_suggested_strong": True}},
        )
    assert resp.status_code == 200
    ge = resp.json()["graph_expansion"]
    assert ge["use_suggested_strong"] is True

    # Persisted to config.json
    config_path = ws / "app" / "config.json"
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["retrieval"]["graph_expansion"]["use_suggested_strong"] is True


@pytest.mark.anyio
async def test_patch_retrieval_rejects_unknown_key(ws):
    from httpx import ASGITransport, AsyncClient
    from main import app
    from models.database import init_database
    await init_database(ws / "app" / "jarvis.db")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/api/settings/retrieval",
            json={"graph_expansion": {"unknown_flag": True}},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Verify expansion weights use loaded config
# ---------------------------------------------------------------------------

def test_use_suggested_strong_false_has_zero_weight(ws):
    from services.retrieval.pipeline import _get_expansion_weights, _load_graph_expansion_config
    cfg = _load_graph_expansion_config(ws)  # defaults
    w = _get_expansion_weights(**cfg)
    assert w["suggested_related"] == 0.0


def test_use_related_false_zeros_related_weight(ws):
    from services.retrieval.pipeline import _get_expansion_weights
    w = _get_expansion_weights(use_related=False)
    assert w["related"] == 0.0


def test_use_part_of_false_zeros_part_of_weight(ws):
    from services.retrieval.pipeline import _get_expansion_weights
    w = _get_expansion_weights(use_part_of=False)
    assert w["part_of"] == 0.0
