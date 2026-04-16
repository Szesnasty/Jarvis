"""Tests for local model support — ollama service + router."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ── Tier Classification ──────────────────────────────────────────────────────


class TestClassifyTier:
    def test_light(self):
        from services.ollama_service import classify_tier
        assert classify_tier(8.0) == "light"
        assert classify_tier(12.0) == "light"
        assert classify_tier(15.9) == "light"

    def test_balanced(self):
        from services.ollama_service import classify_tier
        assert classify_tier(16.0) == "balanced"
        assert classify_tier(24.0) == "balanced"
        assert classify_tier(31.9) == "balanced"

    def test_strong(self):
        from services.ollama_service import classify_tier
        assert classify_tier(32.0) == "strong"
        assert classify_tier(40.0) == "strong"
        assert classify_tier(47.9) == "strong"

    def test_workstation(self):
        from services.ollama_service import classify_tier
        assert classify_tier(48.0) == "workstation"
        assert classify_tier(64.0) == "workstation"
        assert classify_tier(128.0) == "workstation"


# ── Model Scoring ────────────────────────────────────────────────────────────


class TestScoreModel:
    def _make_hw(self, ram=32.0, disk=100.0, gpu="apple", apple_silicon=True):
        from services.ollama_service import HardwareProfile
        return HardwareProfile(
            os="macos",
            arch="arm64",
            total_ram_gb=ram,
            free_disk_gb=disk,
            cpu_cores=10,
            gpu_vendor=gpu,
            is_apple_silicon=apple_silicon,
            tier="strong" if ram >= 32 else "balanced",
        )

    def test_great_compat_small_model_big_ram(self):
        from services.ollama_service import score_model, get_model_by_id

        hw = self._make_hw(ram=32.0)
        model = get_model_by_id("qwen3-1.7b")
        rec = score_model(model, hw, [])
        assert rec.compatibility == "great"
        assert rec.score >= 80

    def test_warning_big_model_small_ram(self):
        from services.ollama_service import score_model, get_model_by_id

        hw = self._make_hw(ram=16.0, gpu=None, apple_silicon=False)
        model = get_model_by_id("gemma4-27b")
        rec = score_model(model, hw, [])
        assert rec.compatibility in ("warning", "unsupported")

    def test_unsupported_not_enough_disk(self):
        from services.ollama_service import score_model, get_model_by_id

        hw = self._make_hw(ram=64.0, disk=5.0)  # 5 GB disk, model needs 18 GB
        model = get_model_by_id("gemma4-27b")
        rec = score_model(model, hw, [])
        assert rec.compatibility == "unsupported"
        assert rec.score == 0
        assert "disk" in rec.reason.lower()

    def test_installed_detection(self):
        from services.ollama_service import score_model, get_model_by_id

        hw = self._make_hw(ram=32.0)
        model = get_model_by_id("qwen3-8b")
        rec = score_model(model, hw, ["qwen3:8b"])
        assert rec.installed is True

    def test_active_detection(self):
        from services.ollama_service import score_model, get_model_by_id

        hw = self._make_hw(ram=32.0)
        model = get_model_by_id("qwen3-8b")
        rec = score_model(model, hw, [], active_model_id="qwen3-8b")
        assert rec.active is True

    def test_cpu_friendly_bonus(self):
        from services.ollama_service import score_model, get_model_by_id

        hw = self._make_hw(ram=16.0, gpu=None, apple_silicon=False)
        model = get_model_by_id("qwen3-1.7b")
        rec = score_model(model, hw, [])
        # cpu_friendly model on CPU-only machine should get bonus
        assert rec.score >= 80


class TestRecommendTop3:
    @pytest.mark.anyio
    async def test_recommend_marks_top_3(self):
        from services.ollama_service import build_catalog, HardwareProfile

        hw = HardwareProfile(
            os="macos", arch="arm64", total_ram_gb=32.0, free_disk_gb=100.0,
            cpu_cores=10, gpu_vendor="apple", is_apple_silicon=True, tier="strong",
        )

        with patch("services.ollama_service.list_installed_models", new_callable=AsyncMock, return_value=[]):
            catalog = await build_catalog(hw, active_model_id=None)

        recommended = [m for m in catalog if m.recommended]
        assert len(recommended) == 3
        # All recommended should be compatible
        for m in recommended:
            assert m.compatibility in ("great", "good")


# ── Hardware Probe ───────────────────────────────────────────────────────────


class TestHardwareProbe:
    def test_returns_valid_profile(self):
        from services.ollama_service import probe_hardware

        hw = probe_hardware()
        assert hw.os in ("macos", "linux", "windows")
        assert hw.arch in ("arm64", "x64")
        assert hw.total_ram_gb > 0
        assert hw.cpu_cores > 0
        assert hw.tier in ("light", "balanced", "strong", "workstation")


# ── Runtime Probe ────────────────────────────────────────────────────────────


class TestRuntimeProbe:
    @pytest.mark.anyio
    async def test_ollama_not_running(self):
        from services.ollama_service import probe_runtime

        # Probe a port that's almost certainly not Ollama
        status = await probe_runtime("http://localhost:19999")
        assert status.running is False
        assert status.reachable is False

    @pytest.mark.anyio
    async def test_runtime_returns_status_object(self):
        from services.ollama_service import probe_runtime

        status = await probe_runtime()
        assert status.runtime == "ollama"
        assert isinstance(status.installed, bool)
        assert isinstance(status.running, bool)


# ── Model Catalog ────────────────────────────────────────────────────────────


class TestModelCatalog:
    def test_catalog_has_7_entries(self):
        from services.ollama_service import get_catalog

        catalog = get_catalog()
        assert len(catalog) == 7

    def test_all_presets_present(self):
        from services.ollama_service import get_catalog

        presets = {m.preset for m in get_catalog()}
        expected = {"fast", "everyday", "balanced", "long-docs", "reasoning", "code", "best-local"}
        assert presets == expected

    def test_litellm_model_has_prefix(self):
        from services.ollama_service import get_catalog

        for m in get_catalog():
            assert m.litellm_model.startswith("ollama_chat/")

    def test_lookup_by_id(self):
        from services.ollama_service import get_model_by_id

        model = get_model_by_id("qwen3-8b")
        assert model is not None
        assert model.label == "Qwen3 8B"
        assert model.preset == "balanced"

    def test_lookup_missing_returns_none(self):
        from services.ollama_service import get_model_by_id

        assert get_model_by_id("nonexistent") is None


# ── LLMConfig Changes ───────────────────────────────────────────────────────


class TestLLMConfig:
    def test_api_base_field(self):
        from services.llm_service import LLMConfig

        config = LLMConfig(
            provider="ollama",
            model="ollama_chat/qwen3:8b",
            api_key="ollama",
            api_base="http://localhost:11434",
        )
        assert config.api_base == "http://localhost:11434"

    def test_timeout_field(self):
        from services.llm_service import LLMConfig

        config = LLMConfig(
            provider="ollama",
            model="ollama_chat/qwen3:8b",
            api_key="ollama",
            timeout=600,
        )
        assert config.timeout == 600

    def test_defaults_are_none(self):
        from services.llm_service import LLMConfig

        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="sk-test",
        )
        assert config.api_base is None
        assert config.timeout is None


class TestLLMServiceResolveModel:
    def test_ollama_model_keeps_prefix(self):
        from services.llm_service import LLMConfig, LLMService

        config = LLMConfig(
            provider="ollama",
            model="ollama_chat/qwen3:8b",
            api_key="ollama",
        )
        svc = LLMService(config)
        assert svc._litellm_model == "ollama_chat/qwen3:8b"

    def test_ollama_model_adds_prefix(self):
        from services.llm_service import LLMConfig, LLMService

        config = LLMConfig(
            provider="ollama",
            model="qwen3:8b",
            api_key="ollama",
        )
        svc = LLMService(config)
        assert svc._litellm_model == "ollama_chat/qwen3:8b"

    def test_openai_model_unchanged(self):
        from services.llm_service import LLMConfig, LLMService

        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key="sk-test",
        )
        svc = LLMService(config)
        assert svc._litellm_model == "gpt-4o"

    def test_google_model_gets_prefix(self):
        from services.llm_service import LLMConfig, LLMService

        config = LLMConfig(
            provider="google",
            model="gemini-2.5-flash",
            api_key="test",
        )
        svc = LLMService(config)
        assert svc._litellm_model == "gemini/gemini-2.5-flash"


# ── Chat.py _make_llm ───────────────────────────────────────────────────────


class TestMakeLlm:
    def test_ollama_returns_llm_service(self):
        from routers.chat import _make_llm
        from services.llm_service import LLMService

        llm = _make_llm("ollama", "ollama_chat/qwen3:8b", "")
        assert isinstance(llm, LLMService)
        assert llm.config.provider == "ollama"
        assert llm.config.api_base == "http://localhost:11434"

    def test_ollama_custom_base_url(self):
        from routers.chat import _make_llm
        from services.llm_service import LLMService

        llm = _make_llm("ollama", "ollama_chat/qwen3:8b", "", base_url="http://myhost:9999")
        assert isinstance(llm, LLMService)
        assert llm.config.api_base == "http://myhost:9999"

    def test_ollama_timeout_is_600(self):
        from routers.chat import _make_llm

        llm = _make_llm("ollama", "ollama_chat/qwen3:8b", "")
        assert llm.config.timeout == 600

    def test_anthropic_returns_claude_service(self):
        from routers.chat import _make_llm
        from services.claude import ClaudeService

        llm = _make_llm(None, None, "sk-ant-test")
        assert isinstance(llm, ClaudeService)

    def test_openai_returns_llm_service(self):
        from routers.chat import _make_llm
        from services.llm_service import LLMService

        llm = _make_llm("openai", "gpt-4o", "sk-test")
        assert isinstance(llm, LLMService)
        assert llm.config.provider == "openai"


# ── Provider Timeout Map ────────────────────────────────────────────────────


class TestProviderTimeouts:
    def test_ollama_timeout(self):
        from services.llm_service import PROVIDER_TIMEOUTS
        assert PROVIDER_TIMEOUTS["ollama"] == 600

    def test_cloud_timeouts(self):
        from services.llm_service import PROVIDER_TIMEOUTS
        assert PROVIDER_TIMEOUTS["anthropic"] == 120
        assert PROVIDER_TIMEOUTS["openai"] == 120
        assert PROVIDER_TIMEOUTS["google"] == 120


# ── Active Model Config ─────────────────────────────────────────────────────


class TestActiveModelConfig:
    def test_set_and_get(self, tmp_path):
        """Test setting and getting active local model via config.json."""
        from services.ollama_service import (
            set_active_local_model,
            get_active_local_model,
            clear_active_local_model,
        )

        # Patch config.get_settings which is imported lazily
        with patch("config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.workspace_path = tmp_path
            mock_settings.return_value = settings

            # Create app dir
            (tmp_path / "app").mkdir()

            set_active_local_model("qwen3-8b", "ollama_chat/qwen3:8b")
            active = get_active_local_model()
            assert active is not None
            assert active["model_id"] == "qwen3-8b"
            assert active["litellm_model"] == "ollama_chat/qwen3:8b"
            assert active["active"] is True

            clear_active_local_model()
            active = get_active_local_model()
            assert active is None  # active=False means get returns None


# ── Router Endpoint Tests (using FastAPI test client) ────────────────────────


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from main import create_app
    from httpx import ASGITransport

    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestLocalModelsAPI:
    @pytest.mark.anyio
    async def test_hardware_endpoint(self, client):
        resp = await client.get("/api/local/hardware")
        assert resp.status_code == 200
        data = resp.json()
        assert "os" in data
        assert "total_ram_gb" in data
        assert "tier" in data

    @pytest.mark.anyio
    async def test_runtime_endpoint(self, client):
        resp = await client.get("/api/local/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runtime"] == "ollama"
        assert "installed" in data
        assert "running" in data

    @pytest.mark.anyio
    async def test_catalog_endpoint(self, client):
        with patch("services.ollama_service.list_installed_models", new_callable=AsyncMock, return_value=[]):
            resp = await client.get("/api/local/models/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7
        # Check that recommendations are scored
        for item in data:
            assert "compatibility" in item
            assert "score" in item
            assert "recommended" in item

    @pytest.mark.anyio
    async def test_select_endpoint(self, client, tmp_path):
        with patch("config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.workspace_path = tmp_path
            mock_settings.return_value = settings
            (tmp_path / "app").mkdir()

            resp = await client.post("/api/local/models/select", json={
                "model_id": "qwen3-8b",
                "litellm_model": "ollama_chat/qwen3:8b",
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
