import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from services.workspace_service import (
    WorkspaceExistsError,
    create_workspace,
    get_workspace_status,
    workspace_exists,
)


@pytest.fixture
def ws_path(tmp_path):
    return tmp_path / "Jarvis"


def test_workspace_not_exists_initially(ws_path):
    assert workspace_exists(ws_path) is False


def test_create_workspace_creates_dirs(ws_path):
    create_workspace(ws_path)
    assert (ws_path / "memory").is_dir()
    assert (ws_path / "memory" / "inbox").is_dir()
    assert (ws_path / "memory" / "daily").is_dir()
    assert (ws_path / "memory" / "projects").is_dir()
    assert (ws_path / "memory" / "people").is_dir()
    assert (ws_path / "memory" / "areas").is_dir()
    assert (ws_path / "memory" / "plans").is_dir()
    assert (ws_path / "memory" / "knowledge").is_dir()
    assert (ws_path / "app").is_dir()
    assert (ws_path / "app" / "sessions").is_dir()
    assert (ws_path / "app" / "cache").is_dir()
    assert (ws_path / "app" / "logs").is_dir()
    assert (ws_path / "agents").is_dir()
    assert (ws_path / "graph").is_dir()


def test_create_workspace_creates_config(ws_path):
    create_workspace(ws_path)
    assert (ws_path / "app" / "config.json").exists()


def test_config_api_key_set_false_browser_storage(ws_path):
    """Browser-only architecture: config always has api_key_set=False, key_storage=browser."""
    create_workspace(ws_path)
    config = json.loads((ws_path / "app" / "config.json").read_text())
    assert config["api_key_set"] is False
    assert config["key_storage"] == "browser"


def test_config_does_not_contain_raw_key(ws_path):
    """No API key should ever appear in config.json."""
    create_workspace(ws_path)
    config_text = (ws_path / "app" / "config.json").read_text()
    assert "sk-ant" not in config_text


def test_workspace_exists_after_creation(ws_path):
    create_workspace(ws_path)
    assert workspace_exists(ws_path) is True


def test_create_workspace_twice_raises(ws_path):
    create_workspace(ws_path)
    with pytest.raises(WorkspaceExistsError):
        create_workspace(ws_path)


def test_workspace_path_from_settings(ws_path):
    with patch("services.workspace_service.get_settings") as mock_settings:
        mock_settings.return_value.workspace_path = ws_path
        create_workspace()
    assert workspace_exists(ws_path) is True


def test_workspace_folder_permissions(ws_path):
    create_workspace(ws_path)
    mode = ws_path.stat().st_mode
    assert mode & stat.S_IRUSR  # owner-readable

