"""Central privacy / network kill-switches.

Single source of truth for "is this outbound network call allowed?".

Three layers, in priority order:
1. Environment variable ``JARVIS_OFFLINE_MODE=1`` — hard lock, UI cannot override.
2. Per-workspace preference ``privacy_offline_mode`` — user toggle in Settings.
3. Per-feature preferences (``privacy_web_search_enabled``,
   ``privacy_url_ingest_enabled``, ``privacy_cloud_providers_enabled``).

When offline mode is active, all per-feature toggles are forced off regardless
of their stored value. This guarantees that flipping the master switch
immediately blocks every outbound integration without having to re-toggle each
sub-setting.

Local-only providers (Ollama, fastembed, local reranker) are NEVER blocked
by these switches — they don't touch the public internet.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from config import get_settings
from services import preference_service

_ENV_FLAG = "JARVIS_OFFLINE_MODE"

# Local-only provider IDs — never blocked by offline mode.
LOCAL_PROVIDERS = frozenset({"ollama"})


class PrivacyBlockedError(RuntimeError):
    """Raised when an outbound integration is blocked by privacy settings."""


def _env_force_offline() -> bool:
    return os.environ.get(_ENV_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def _ws(workspace_path: Optional[Path] = None) -> Path:
    return workspace_path or get_settings().workspace_path


def _bool_pref(prefs: dict, key: str, default: bool) -> bool:
    raw = prefs.get(key)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def get_privacy_settings(workspace_path: Optional[Path] = None) -> dict:
    """Return current effective privacy settings.

    ``offline_mode_locked`` is True when the env var forces offline mode — the
    UI should disable the toggle in that case.
    """
    prefs = preference_service.load_preferences(workspace_path=_ws(workspace_path))
    env_locked = _env_force_offline()
    user_offline = _bool_pref(prefs, "privacy_offline_mode", False)
    offline = env_locked or user_offline

    # Defaults: cloud providers + url ingest opt-in by feature, web search ON
    # but gated behind explicit user click in UI. We default everything to ON
    # to preserve current behaviour for existing users; the kill switches are
    # opt-in protections.
    web_search = _bool_pref(prefs, "privacy_web_search_enabled", True)
    url_ingest = _bool_pref(prefs, "privacy_url_ingest_enabled", True)
    cloud = _bool_pref(prefs, "privacy_cloud_providers_enabled", True)

    if offline:
        web_search = False
        url_ingest = False
        cloud = False

    return {
        "offline_mode": offline,
        "offline_mode_locked": env_locked,
        "web_search_enabled": web_search,
        "url_ingest_enabled": url_ingest,
        "cloud_providers_enabled": cloud,
    }


def is_offline_mode(workspace_path: Optional[Path] = None) -> bool:
    return get_privacy_settings(workspace_path)["offline_mode"]


def web_search_enabled(workspace_path: Optional[Path] = None) -> bool:
    return get_privacy_settings(workspace_path)["web_search_enabled"]


def url_ingest_enabled(workspace_path: Optional[Path] = None) -> bool:
    return get_privacy_settings(workspace_path)["url_ingest_enabled"]


def cloud_providers_enabled(workspace_path: Optional[Path] = None) -> bool:
    return get_privacy_settings(workspace_path)["cloud_providers_enabled"]


def is_local_provider(provider: Optional[str]) -> bool:
    return (provider or "").strip().lower() in LOCAL_PROVIDERS


def assert_provider_allowed(provider: Optional[str], workspace_path: Optional[Path] = None) -> None:
    """Raise PrivacyBlockedError if a non-local provider is used while blocked."""
    if is_local_provider(provider):
        return
    if not cloud_providers_enabled(workspace_path):
        if is_offline_mode(workspace_path):
            raise PrivacyBlockedError(
                "Offline mode is enabled — cloud LLM providers are blocked. "
                "Disable offline mode in Settings → Privacy or use a local Ollama model."
            )
        raise PrivacyBlockedError(
            "Cloud LLM providers are disabled in Settings → Privacy. "
            "Enable them or switch to a local Ollama model."
        )


_ALLOWED_PRIVACY_KEYS = {
    "offline_mode": "privacy_offline_mode",
    "web_search_enabled": "privacy_web_search_enabled",
    "url_ingest_enabled": "privacy_url_ingest_enabled",
    "cloud_providers_enabled": "privacy_cloud_providers_enabled",
}


def update_privacy_settings(
    updates: dict,
    workspace_path: Optional[Path] = None,
) -> dict:
    """Apply a partial update of privacy preferences.

    Unknown keys are rejected. Returns the new effective settings.
    Raises ``PrivacyBlockedError`` if the env lock is engaged and the caller
    tries to disable offline mode.
    """
    ws = _ws(workspace_path)
    env_locked = _env_force_offline()

    for key, value in updates.items():
        if key not in _ALLOWED_PRIVACY_KEYS:
            raise ValueError(f"Unknown privacy setting: {key}")
        if key == "offline_mode" and env_locked and not value:
            raise PrivacyBlockedError(
                f"Offline mode is locked by the {_ENV_FLAG} environment variable "
                "and cannot be disabled from the UI."
            )
        pref_key = _ALLOWED_PRIVACY_KEYS[key]
        preference_service.save_preference(
            pref_key,
            "true" if value else "false",
            workspace_path=ws,
        )

    return get_privacy_settings(ws)
