"""Tests for step 21d — local model integration, tool calling & resilience."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Tool Mode ────────────────────────────────────────────────────────────────


class TestToolMode:
    def test_tool_mode_native(self):
        from services.ollama_service import get_model_by_id, _tool_mode_for

        model = get_model_by_id("qwen3-8b")
        assert model.native_tools is True
        assert _tool_mode_for(model) == "native"

    def test_tool_mode_json_fallback(self):
        from services.ollama_service import get_model_by_id, _tool_mode_for

        model = get_model_by_id("qwen3-4b")
        assert model.native_tools is False
        assert _tool_mode_for(model) == "json_fallback"

    def test_tool_mode_limited(self):
        from services.ollama_service import get_model_by_id, _tool_mode_for

        model = get_model_by_id("qwen3-1.7b")
        assert model.native_tools is False
        # download_size < 2 GB → limited
        assert _tool_mode_for(model) == "limited"

    def test_recommendation_includes_tool_mode(self):
        from services.ollama_service import score_model, get_model_by_id, HardwareProfile

        hw = HardwareProfile(
            os="macos", arch="arm64", total_ram_gb=32.0, free_disk_gb=100.0,
            cpu_cores=10, gpu_vendor="apple", is_apple_silicon=True, tier="strong",
        )
        model = get_model_by_id("qwen3-8b")
        rec = score_model(model, hw, [])
        assert rec.tool_mode == "native"

    def test_recommendation_tool_mode_fallback(self):
        from services.ollama_service import score_model, get_model_by_id, HardwareProfile

        hw = HardwareProfile(
            os="macos", arch="arm64", total_ram_gb=32.0, free_disk_gb=100.0,
            cpu_cores=10, gpu_vendor="apple", is_apple_silicon=True, tier="strong",
        )
        model = get_model_by_id("ministral-3-8b")
        rec = score_model(model, hw, [])
        assert rec.tool_mode == "json_fallback"


# ── Timeout Configuration ───────────────────────────────────────────────────


class TestTimeoutConfig:
    def test_ollama_timeout_600(self):
        from services.llm_service import PROVIDER_TIMEOUTS

        assert PROVIDER_TIMEOUTS["ollama"] == 600

    def test_cloud_timeout_120(self):
        from services.llm_service import PROVIDER_TIMEOUTS

        for provider in ("anthropic", "openai", "google"):
            assert PROVIDER_TIMEOUTS[provider] == 120

    def test_make_llm_ollama_timeout(self):
        from routers.chat import _make_llm

        llm = _make_llm("ollama", "ollama_chat/qwen3:8b", "")
        assert llm.config.timeout == 600

    def test_make_llm_ollama_no_api_key_needed(self):
        from routers.chat import _make_llm

        llm = _make_llm("ollama", "ollama_chat/qwen3:8b", "")
        assert llm.config.api_key == "ollama"

    def test_make_llm_ollama_custom_base_url(self):
        from routers.chat import _make_llm

        llm = _make_llm("ollama", "ollama_chat/qwen3:8b", "", base_url="http://myhost:9999")
        assert llm.config.api_base == "http://myhost:9999"


# ── Warm-up Endpoint ────────────────────────────────────────────────────────


class TestWarmUp:
    @pytest.mark.anyio
    async def test_warm_up_success(self):
        from services.ollama_service import warm_up_model

        mock_resp = AsyncMock()
        mock_resp.status_code = 200

        with patch("services.ollama_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await warm_up_model("qwen3:8b")
            assert result is True

    @pytest.mark.anyio
    async def test_warm_up_connection_error(self):
        import httpx
        from services.ollama_service import warm_up_model

        with patch("services.ollama_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await warm_up_model("qwen3:8b")
            assert result is False


# ── Test Endpoint ────────────────────────────────────────────────────────────


class TestTestEndpoint:
    @pytest.mark.anyio
    async def test_test_model_success(self):
        from services.ollama_service import test_model

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Hello! How can I help?"},
            "eval_count": 10,
            "eval_duration": 1_000_000_000,  # 1 second
        }

        with patch("services.ollama_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await test_model("qwen3:8b")
            assert result.success is True
            assert "Hello" in result.response_text
            assert result.tokens_per_second == 10.0
            assert result.tool_mode == "native"  # qwen3:8b has native tools

    @pytest.mark.anyio
    async def test_test_model_ollama_not_running(self):
        import httpx
        from services.ollama_service import test_model

        with patch("services.ollama_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await test_model("qwen3:8b")
            assert result.success is False
            assert "Cannot connect" in result.error

    @pytest.mark.anyio
    async def test_test_model_returns_tool_mode_for_unknown(self):
        """Unknown models should get json_fallback."""
        from services.ollama_service import test_model

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Hi"},
            "eval_count": 5,
            "eval_duration": 500_000_000,
        }

        with patch("services.ollama_service.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await test_model("some-unknown-model:latest")
            assert result.success is True
            assert result.tool_mode == "json_fallback"


# ── Catalog has tool_mode ────────────────────────────────────────────────────


class TestCatalogToolMode:
    @pytest.mark.anyio
    async def test_catalog_entries_have_tool_mode(self):
        from services.ollama_service import build_catalog, HardwareProfile

        hw = HardwareProfile(
            os="macos", arch="arm64", total_ram_gb=32.0, free_disk_gb=100.0,
            cpu_cores=10, gpu_vendor="apple", is_apple_silicon=True, tier="strong",
        )

        with patch("services.ollama_service.list_installed_models", new_callable=AsyncMock, return_value=[]):
            catalog = await build_catalog(hw)

        for rec in catalog:
            assert rec.tool_mode in ("native", "json_fallback", "limited"), \
                f"{rec.model_id} has unexpected tool_mode: {rec.tool_mode}"
