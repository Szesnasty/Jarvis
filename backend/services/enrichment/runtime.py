"""Runtime/config helpers for enrichment service."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import get_settings
from services.ollama_service import (
    DEFAULT_OLLAMA_BASE_URL,
    _normalize_and_validate_ollama_base_url,
    get_active_local_model,
    probe_hardware,
)
from services import preference_service

from .models import DEFAULT_BUSINESS_AREAS


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def workspace(workspace_path: Optional[Path] = None) -> Path:
    return workspace_path or get_settings().workspace_path


def db_path(workspace_path: Optional[Path] = None) -> Path:
    ws = workspace(workspace_path)
    return ws / "app" / "jarvis.db"


def prompt_dir() -> Path:
    return Path(__file__).parent / "prompts"


def load_prompt_template(name: str) -> str:
    p = prompt_dir() / name
    return p.read_text(encoding="utf-8")


def load_business_areas(workspace_path: Optional[Path] = None) -> list[str]:
    ws = workspace(workspace_path)
    cfg = ws / "memory" / "jira" / "_config.json"
    if not cfg.exists():
        return DEFAULT_BUSINESS_AREAS

    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_BUSINESS_AREAS

    raw = data.get("business_areas")
    if not isinstance(raw, list):
        return DEFAULT_BUSINESS_AREAS

    cleaned = []
    for item in raw:
        token = str(item or "").strip().lower().replace(" ", "_")
        if token and token not in cleaned:
            cleaned.append(token)

    if "unknown" not in cleaned:
        cleaned.append("unknown")

    return cleaned or DEFAULT_BUSINESS_AREAS


def select_model_id(workspace_path: Optional[Path] = None) -> str:
    ws = workspace(workspace_path)
    config_path = ws / "app" / "config.json"

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            enrichment = data.get("enrichment")
            if isinstance(enrichment, dict):
                configured = str(enrichment.get("model_id") or "").strip()
                if configured:
                    if configured.startswith("ollama_chat/"):
                        return configured
                    return f"ollama_chat/{configured}"
        except (OSError, json.JSONDecodeError):
            pass

    active = get_active_local_model()
    if active and active.get("active"):
        litellm_model = str(active.get("litellm_model") or "").strip()
        if litellm_model:
            return litellm_model

    try:
        hw = probe_hardware()
        if hw.total_ram_gb < 12:
            return "ollama_chat/qwen3:1.7b"
    except Exception:
        pass

    return "ollama_chat/qwen3:4b"


def select_base_url(workspace_path: Optional[Path] = None) -> str:
    ws = workspace(workspace_path)
    config_path = ws / "app" / "config.json"

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            enrichment = data.get("enrichment")
            if isinstance(enrichment, dict) and enrichment.get("base_url"):
                return _normalize_and_validate_ollama_base_url(str(enrichment["base_url"]))
        except (OSError, json.JSONDecodeError):
            pass

    active = get_active_local_model()
    if active and active.get("base_url"):
        return _normalize_and_validate_ollama_base_url(str(active["base_url"]))

    return DEFAULT_OLLAMA_BASE_URL


def is_on_battery_power() -> bool:
    if os.name == "nt":
        return False

    if subprocess.run(["uname"], capture_output=True, text=True).stdout.strip() == "Darwin":
        try:
            out = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            data = (out.stdout or "") + (out.stderr or "")
            return "Battery Power" in data
        except Exception:
            return False

    ac_online = Path("/sys/class/power_supply/AC/online")
    if ac_online.exists():
        try:
            return ac_online.read_text(encoding="utf-8").strip() == "0"
        except OSError:
            return False

    return False


def should_pause_for_battery(workspace_path: Optional[Path] = None) -> bool:
    """Return True if enrichment should pause due to battery power.

    Respects the user preference 'enrichment_allow_on_battery'.
    """
    if not is_on_battery_power():
        return False
    ws = workspace(workspace_path)
    prefs = preference_service.load_preferences(workspace_path=ws)
    return prefs.get("enrichment_allow_on_battery", "false").lower() != "true"
