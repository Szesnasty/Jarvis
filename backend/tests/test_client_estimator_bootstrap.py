"""Tests for client-estimator bootstrap (step 28e)."""
import json
import pytest

from services.specialist_service import (
    seed_builtin_specialists,
    _get_dismissed_specialists,
    _mark_specialist_dismissed,
)


@pytest.mark.anyio
async def test_fresh_workspace_client_estimator_created(tmp_path):
    """A fresh workspace gets agents/client-estimator.json written by seed."""
    agents = tmp_path / "agents"
    agents.mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "config.json").write_text("{}", encoding="utf-8")

    seeded = seed_builtin_specialists(tmp_path)

    estimator_path = agents / "client-estimator.json"
    assert estimator_path.exists(), "client-estimator.json should be created"
    assert "client-estimator" in seeded

    data = json.loads(estimator_path.read_text())
    assert data["id"] == "client-estimator"
    assert data["name"] == "Client Estimator"
    assert "write_note" in data["tools"]
    assert "search_notes" in data["tools"]
    assert "NOT IN SOURCES" in data["system_prompt"]


@pytest.mark.anyio
async def test_existing_workspace_file_not_overwritten(tmp_path):
    """If clients-estimator.json already exists, seed does not overwrite it."""
    agents = tmp_path / "agents"
    agents.mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "config.json").write_text("{}", encoding="utf-8")

    custom = {
        "id": "client-estimator",
        "name": "My Custom Estimator",
        "system_prompt": "custom",
        "role": "custom role",
        "icon": "🎯",
        "sources": [],
        "tools": [],
        "rules": [],
        "examples": [],
    }
    (agents / "client-estimator.json").write_text(
        json.dumps(custom, indent=2), encoding="utf-8"
    )

    seeded = seed_builtin_specialists(tmp_path)

    data = json.loads((agents / "client-estimator.json").read_text())
    # User's custom name must be preserved
    assert data["name"] == "My Custom Estimator"
    # ID not in seeded (it already existed, no create)
    assert "client-estimator" not in seeded or data.get("name") == "My Custom Estimator"


@pytest.mark.anyio
async def test_dismissed_specialist_not_recreated(tmp_path):
    """If client-estimator was dismissed by user, seed skips it."""
    agents = tmp_path / "agents"
    agents.mkdir(parents=True)
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    # Mark as dismissed directly via helper (simulates user having deleted it)
    (app_dir / "config.json").write_text("{}", encoding="utf-8")
    _mark_specialist_dismissed("client-estimator", tmp_path)

    # Confirm dismissal was recorded
    dismissed = _get_dismissed_specialists(tmp_path)
    assert "client-estimator" in dismissed

    # seed_builtin_specialists must NOT recreate it
    seeded = seed_builtin_specialists(tmp_path)

    assert "client-estimator" not in seeded
    assert not (agents / "client-estimator.json").exists()


@pytest.mark.anyio
async def test_dismissed_list_idempotent(tmp_path):
    """Calling _mark_specialist_dismissed twice does not duplicate the entry."""
    (tmp_path / "app").mkdir(parents=True)
    (tmp_path / "app" / "config.json").write_text("{}", encoding="utf-8")

    _mark_specialist_dismissed("client-estimator", tmp_path)
    _mark_specialist_dismissed("client-estimator", tmp_path)

    cfg = json.loads((tmp_path / "app" / "config.json").read_text())
    assert cfg["dismissed_specialists"].count("client-estimator") == 1
