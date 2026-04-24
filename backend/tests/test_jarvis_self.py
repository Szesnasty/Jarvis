"""Tests for the JARVIS-self specialist.

JARVIS is a built-in, always-active specialist with two user-editable fields
(`system_prompt`, `behavior_extension`). It cannot be deleted, cannot be
toggled via activate/deactivate, and cannot be edited via the generic update
endpoint. Its overrides are wired into `build_system_prompt_with_stats`.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services import specialist_service
from services.specialist_service import (
    JARVIS_SELF_ID,
    SpecialistNotFoundError,
    _BUILTIN_SPECIALISTS,
    seed_builtin_specialists,
    update_jarvis_self,
    get_jarvis_self,
    delete_specialist,
    activate_specialist,
    update_specialist,
)


def _settings_mock(ws: Path):
    mock = MagicMock()
    mock.workspace_path = ws
    return mock


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    (ws / "agents").mkdir(parents=True)
    return ws


# ── Built-in registration ─────────────────────────────────────────────────────


class TestJarvisBuiltin:
    def test_jarvis_in_builtins(self):
        ids = [s["id"] for s in _BUILTIN_SPECIALISTS]
        assert JARVIS_SELF_ID in ids

    def test_jarvis_defaults_are_empty(self):
        spec = next(s for s in _BUILTIN_SPECIALISTS if s["id"] == JARVIS_SELF_ID)
        # The user must NEVER see the default Jarvis SYSTEM_PROMPT pre-filled
        # in the editable field. Empty means "use the built-in default".
        assert spec["system_prompt"] == ""
        assert spec["behavior_extension"] == ""

    def test_seed_creates_jarvis(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            created = seed_builtin_specialists(workspace)
        assert JARVIS_SELF_ID in created
        fp = workspace / "agents" / f"{JARVIS_SELF_ID}.json"
        assert fp.exists()
        data = json.loads(fp.read_text())
        assert data["system_prompt"] == ""
        assert data["behavior_extension"] == ""
        assert data["builtin"] is True


# ── Service layer protections ─────────────────────────────────────────────────


class TestJarvisProtections:
    def test_cannot_delete_jarvis(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            with pytest.raises(ValueError, match="cannot be deleted"):
                delete_specialist(JARVIS_SELF_ID, workspace)
            # File still on disk
            assert (workspace / "agents" / f"{JARVIS_SELF_ID}.json").exists()

    def test_cannot_activate_jarvis(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            with pytest.raises(ValueError, match="always active"):
                activate_specialist(JARVIS_SELF_ID, workspace)

    def test_cannot_generic_update_jarvis(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            with pytest.raises(ValueError, match="cannot be edited"):
                update_specialist(JARVIS_SELF_ID, {"name": "Hacked"}, workspace)


# ── update_jarvis_self ───────────────────────────────────────────────────────


class TestJarvisUpdate:
    def test_update_writes_only_whitelisted_fields(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            spec = update_jarvis_self(
                {
                    "system_prompt": "Always reply in haiku.",
                    "behavior_extension": "Sign every reply with —J.",
                    "name": "Should be ignored",
                    "icon": "💀",
                },
                workspace,
            )
        assert spec["system_prompt"] == "Always reply in haiku."
        assert spec["behavior_extension"] == "Sign every reply with —J."
        # name/icon untouched
        assert spec["name"] == "JARVIS"
        assert spec["icon"] == "🧠"

    def test_clearing_fields_persists_empty(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            update_jarvis_self({"system_prompt": "first"}, workspace)
            spec = update_jarvis_self({"system_prompt": ""}, workspace)
        assert spec["system_prompt"] == ""

    def test_get_jarvis_self_returns_none_when_unseeded(self, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            assert get_jarvis_self(workspace) is None


# ── System prompt wiring ──────────────────────────────────────────────────────


class TestJarvisSystemPromptWiring:
    @pytest.mark.asyncio
    async def test_default_uses_builtin_system_prompt(self, workspace, monkeypatch):
        from services.claude import SYSTEM_PROMPT, build_system_prompt_with_stats

        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            # Stub context builder to avoid retrieval pipeline.
            async def _empty_ctx(*args, **kwargs):
                return "", 0
            monkeypatch.setattr("services.claude.build_context", _empty_ctx)
            prompt, _ = await build_system_prompt_with_stats(
                "hello", workspace_path=workspace,
            )
        assert SYSTEM_PROMPT.split("\n", 1)[0] in prompt

    @pytest.mark.asyncio
    async def test_override_replaces_default(self, workspace, monkeypatch):
        from services.claude import SYSTEM_PROMPT, build_system_prompt_with_stats

        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            update_jarvis_self(
                {"system_prompt": "MARKER-OVERRIDE-12345"},
                workspace,
            )
            async def _empty_ctx(*args, **kwargs):
                return "", 0
            monkeypatch.setattr("services.claude.build_context", _empty_ctx)
            prompt, _ = await build_system_prompt_with_stats(
                "hello", workspace_path=workspace,
            )
        assert "MARKER-OVERRIDE-12345" in prompt
        # Default Jarvis prompt should NOT be in output when overridden.
        # Use a sentinel substring that is unique to the default SYSTEM_PROMPT.
        # The first ~60 chars of SYSTEM_PROMPT are highly likely unique.
        sentinel = SYSTEM_PROMPT.strip().split("\n", 1)[0][:60]
        if sentinel and sentinel != "MARKER-OVERRIDE-12345":
            assert sentinel not in prompt

    @pytest.mark.asyncio
    async def test_extension_appends_after_base(self, workspace, monkeypatch):
        from services.claude import build_system_prompt_with_stats

        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            update_jarvis_self(
                {"behavior_extension": "MARKER-EXT-99999 must always be cited."},
                workspace,
            )
            async def _empty_ctx(*args, **kwargs):
                return "", 0
            monkeypatch.setattr("services.claude.build_context", _empty_ctx)
            prompt, _ = await build_system_prompt_with_stats(
                "hello", workspace_path=workspace,
            )
        assert "MARKER-EXT-99999" in prompt
        assert "JARVIS — user-defined behavior extensions" in prompt


# ── HTTP layer ────────────────────────────────────────────────────────────────


class TestJarvisHttpEndpoints:
    @pytest.mark.asyncio
    async def test_get_config_returns_only_user_fields(self, client, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            resp = await client.get("/api/specialists/jarvis/config")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"system_prompt", "behavior_extension"}
        assert body["system_prompt"] == ""
        assert body["behavior_extension"] == ""

    @pytest.mark.asyncio
    async def test_put_config_updates(self, client, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            resp = await client.put(
                "/api/specialists/jarvis/config",
                json={"system_prompt": "new-prompt", "behavior_extension": "new-ext"},
            )
        assert resp.status_code == 200
        assert resp.json()["system_prompt"] == "new-prompt"
        assert resp.json()["behavior_extension"] == "new-ext"

    @pytest.mark.asyncio
    async def test_put_rejects_oversize(self, client, workspace):
        from models.schemas import JARVIS_PROMPT_MAX_CHARS

        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            resp = await client.put(
                "/api/specialists/jarvis/config",
                json={"system_prompt": "x" * (JARVIS_PROMPT_MAX_CHARS + 1)},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_jarvis_returns_403(self, client, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            resp = await client.delete("/api/specialists/jarvis")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_activate_jarvis_returns_400(self, client, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            resp = await client.post("/api/specialists/activate/jarvis")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_generic_put_jarvis_returns_403(self, client, workspace):
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(workspace)
            seed_builtin_specialists(workspace)
            resp = await client.put(
                "/api/specialists/jarvis",
                json={"name": "Hacked"},
            )
        assert resp.status_code == 403
