import json
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
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace("sk-ant-test-key-12345678901234", ws_path)
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
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace("sk-ant-test-key-12345678901234", ws_path)
    assert (ws_path / "app" / "config.json").exists()


def test_config_contains_api_key_set_true(ws_path):
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace("sk-ant-test-key-12345678901234", ws_path)
    config = json.loads((ws_path / "app" / "config.json").read_text())
    assert config["api_key_set"] is True


def test_config_does_not_contain_raw_key(ws_path):
    key = "sk-ant-test-key-12345678901234"
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace(key, ws_path)
    config_text = (ws_path / "app" / "config.json").read_text()
    assert key not in config_text


def test_api_key_stored_in_keyring(ws_path):
    key = "sk-ant-test-key-12345678901234"
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace(key, ws_path)
    mock_kr.set_password.assert_called_once_with("jarvis", "anthropic_api_key", key)


def test_workspace_exists_after_creation(ws_path):
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace("sk-ant-test-key-12345678901234", ws_path)
    assert workspace_exists(ws_path) is True


def test_create_workspace_twice_raises(ws_path):
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace("sk-ant-test-key-12345678901234", ws_path)
    with pytest.raises(WorkspaceExistsError):
        with patch("services.workspace_service.keyring") as mock_kr:
            create_workspace("sk-ant-test-key-12345678901234", ws_path)


def test_workspace_path_from_settings(ws_path):
    with patch("services.workspace_service.get_settings") as mock_settings:
        mock_settings.return_value.workspace_path = ws_path
        with patch("services.workspace_service.keyring"):
            create_workspace("sk-ant-test-key-12345678901234")
    assert workspace_exists(ws_path) is True


def test_create_workspace_with_empty_key_raises(ws_path):
    with pytest.raises(ValueError, match="empty"):
        create_workspace("", ws_path)


def test_create_workspace_with_whitespace_key_raises(ws_path):
    with pytest.raises(ValueError, match="empty"):
        create_workspace("   ", ws_path)


def test_workspace_folder_permissions(ws_path):
    with patch("services.workspace_service.keyring") as mock_kr:
        create_workspace("sk-ant-test-key-12345678901234", ws_path)
    # Check that workspace dirs exist and are readable
    import stat
    mode = ws_path.stat().st_mode
    assert mode & stat.S_IRUSR  # owner-readable
