import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import keyring
from keyring.errors import NoKeyringError

from config import get_settings

logger = logging.getLogger(__name__)

WORKSPACE_DIRS = [
    "app",
    "app/sessions",
    "app/cache",
    "app/logs",
    "app/audio",
    "memory",
    "memory/inbox",
    "memory/daily",
    "memory/projects",
    "memory/people",
    "memory/areas",
    "memory/plans",
    "memory/summaries",
    "memory/knowledge",
    "memory/preferences",
    "memory/examples",
    "memory/attachments",
    "graph",
    "agents",
]


class WorkspaceExistsError(Exception):
    pass


def workspace_exists(workspace_path: Optional[Path] = None) -> bool:
    path = workspace_path or get_settings().workspace_path
    config_file = path / "app" / "config.json"
    return config_file.exists()


def get_workspace_status(workspace_path: Optional[Path] = None) -> dict:
    path = workspace_path or get_settings().workspace_path
    if not workspace_exists(path):
        return {"initialized": False}

    config_file = path / "app" / "config.json"
    config = json.loads(config_file.read_text())
    return {
        "initialized": True,
        "workspace_path": str(path),
        "api_key_set": config.get("api_key_set", False),
    }


def create_workspace(api_key: str, workspace_path: Optional[Path] = None) -> dict:
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key must not be empty")

    path = workspace_path or get_settings().workspace_path

    if workspace_exists(path):
        raise WorkspaceExistsError(f"Workspace already exists at {path}")

    # Create directory tree
    for d in WORKSPACE_DIRS:
        (path / d).mkdir(parents=True, exist_ok=True)

    # Store API key
    _store_api_key(api_key, path)

    # Write config.json
    config = {
        "version": "0.1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_key_set": True,
        "workspace_path": str(path),
    }
    config_file = path / "app" / "config.json"
    config_file.write_text(json.dumps(config, indent=2))

    return {"status": "ok", "workspace_path": str(path)}


def _store_api_key(api_key: str, workspace_path: Path) -> None:
    try:
        keyring.set_password("jarvis", "anthropic_api_key", api_key)
    except (NoKeyringError, Exception) as exc:
        logger.warning("keyring unavailable (%s), storing API key in config.json", exc)
        key_file = workspace_path / "app" / "api_key.json"
        key_file.write_text(json.dumps({"api_key": api_key}))
        key_file.chmod(0o600)


def get_api_key(workspace_path: Optional[Path] = None) -> Optional[str]:
    try:
        key = keyring.get_password("jarvis", "anthropic_api_key")
        if key:
            return key
    except (NoKeyringError, Exception):
        pass

    path = workspace_path or get_settings().workspace_path
    key_file = path / "app" / "api_key.json"
    if key_file.exists():
        data = json.loads(key_file.read_text())
        return data.get("api_key")

    return None
