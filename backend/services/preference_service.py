import json
from pathlib import Path
from typing import Dict, Optional

from config import get_settings


def _prefs_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "app" / "preferences.json"


def load_preferences(workspace_path: Optional[Path] = None) -> Dict[str, str]:
    path = _prefs_path(workspace_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_preference(
    key: str,
    value: str,
    workspace_path: Optional[Path] = None,
) -> None:
    if not key or not key.strip():
        raise ValueError("Preference key cannot be empty")
    path = _prefs_path(workspace_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefs = load_preferences(workspace_path)
    prefs[key.strip()] = value
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def delete_preference(key: str, workspace_path: Optional[Path] = None) -> None:
    path = _prefs_path(workspace_path)
    if not path.exists():
        return
    prefs = load_preferences(workspace_path)
    prefs.pop(key, None)
    path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


def format_for_prompt(workspace_path: Optional[Path] = None) -> Optional[str]:
    prefs = load_preferences(workspace_path)
    if not prefs:
        return None
    lines = [f"- [{k}] {v}" for k, v in prefs.items()]
    return "User preferences:\n" + "\n".join(lines)
