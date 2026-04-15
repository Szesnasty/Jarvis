import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    try:
        config = json.loads(config_file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read config.json: %s", exc)
        return {"initialized": False}

    # Keys live in the browser (localStorage/sessionStorage).
    # The env var is only used for dev/CI — never stored server-side.
    env_key_available = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "initialized": True,
        "workspace_path": str(path),
        "api_key_set": env_key_available,
        "key_storage": "environment" if env_key_available else "browser",
    }


def create_workspace(workspace_path: Optional[Path] = None) -> dict:
    path = workspace_path or get_settings().workspace_path

    if workspace_exists(path):
        raise WorkspaceExistsError(f"Workspace already exists at {path}")

    # Create directory tree
    for d in WORKSPACE_DIRS:
        (path / d).mkdir(parents=True, exist_ok=True)

    try:
        config = {
            "version": "0.1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            # Keys are managed entirely in the browser (localStorage/sessionStorage).
            # The backend never stores or retrieves API keys.
            "api_key_set": False,
            "key_storage": "browser",
            "workspace_path": str(path),
        }
        config_file = path / "app" / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
    except Exception:
        import shutil
        shutil.rmtree(path, ignore_errors=True)
        raise

    return {"status": "ok", "workspace_path": str(path)}


def get_api_key(workspace_path: Optional[Path] = None) -> Optional[str]:
    """Return key from environment only (used for dev/CI). Browser keys are
    sent per-request and never reach this function in production."""
    return os.environ.get("ANTHROPIC_API_KEY") or None
