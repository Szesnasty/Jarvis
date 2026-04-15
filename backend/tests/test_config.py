import os
from pathlib import Path

import pytest


def test_default_workspace_path(monkeypatch):
    monkeypatch.delenv("JARVIS_WORKSPACE_PATH", raising=False)
    from config import Settings

    s = Settings()
    assert s.workspace_path == Path.home() / "Jarvis"


def test_default_host_is_localhost():
    from config import Settings

    s = Settings()
    assert s.api_host == "127.0.0.1"


def test_default_port():
    from config import Settings

    s = Settings()
    assert s.api_port == 8000


def test_cors_includes_nuxt():
    from config import Settings

    s = Settings()
    assert "http://localhost:3000" in s.cors_origins


def test_env_override(monkeypatch):
    monkeypatch.setenv("JARVIS_API_PORT", "9999")
    from config import Settings

    s = Settings()
    assert s.api_port == 9999
