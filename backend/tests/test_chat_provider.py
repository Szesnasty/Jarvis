"""Tests for multi-provider chat routing via WebSocket."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from services.claude import StreamEvent

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def isolate_workspace(tmp_path, monkeypatch):
    """Prevent tests from touching the real workspace."""
    settings = MagicMock()
    settings.workspace_path = tmp_path
    for mod in ["services.session_service", "services.memory_service",
                "services.graph_service", "services.context_builder",
                "services.preference_service", "services.token_tracking",
                "services.workspace_service"]:
        try:
            monkeypatch.setattr(f"{mod}.get_settings", lambda: settings)
        except AttributeError:
            pass
    for d in ["app", "app/sessions", "app/logs", "memory", "memory/inbox",
              "memory/preferences", "graph"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)


def _fake_stream(*events):
    async def _gen(**kwargs):
        for e in events:
            yield e
    return _gen


@pytest.fixture
def mock_no_server_key():
    """No server-stored key — forces client key requirement."""
    with patch("routers.chat.get_api_key", return_value=None):
        yield


@pytest.fixture
def mock_server_key():
    """Server has an Anthropic key."""
    with patch("routers.chat.get_api_key", return_value="sk-ant-server-key"):
        yield


# ── Provider routing tests ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_ws_openai_provider_uses_llm_service(mock_no_server_key):
    """Sending provider=openai should create LLMService, not ClaudeService."""
    from starlette.testclient import TestClient

    with patch("routers.chat.LLMService") as mock_llm_cls, \
         patch("routers.chat.ClaudeService") as mock_claude_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.stream_response = _fake_stream(
            StreamEvent(type="text_delta", content="GPT says hi"),
            StreamEvent(type="done"),
        )
        mock_llm.close = AsyncMock()

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({
                    "content": "Hello",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-openai-test",
                })

                events = []
                while True:
                    msg = ws.receive_json()
                    events.append(msg)
                    if msg["type"] == "done":
                        break

        # LLMService should have been created, not ClaudeService
        mock_llm_cls.assert_called_once()
        mock_claude_cls.assert_not_called()

        text = [e for e in events if e["type"] == "text_delta"]
        assert text[0]["content"] == "GPT says hi"


@pytest.mark.anyio
async def test_ws_anthropic_provider_uses_claude_service(mock_no_server_key):
    """Sending provider=anthropic should use ClaudeService (native)."""
    from starlette.testclient import TestClient

    with patch("routers.chat.ClaudeService") as mock_claude_cls, \
         patch("routers.chat.LLMService") as mock_llm_cls:
        mock_claude = mock_claude_cls.return_value
        mock_claude.stream_response = _fake_stream(
            StreamEvent(type="text_delta", content="Claude says hi"),
            StreamEvent(type="done"),
        )
        mock_claude.close = AsyncMock()

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({
                    "content": "Hello",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "api_key": "sk-ant-test",
                })

                events = []
                while True:
                    msg = ws.receive_json()
                    events.append(msg)
                    if msg["type"] == "done":
                        break

        # ClaudeService for Anthropic, not LLMService
        mock_claude_cls.assert_called_once()
        mock_llm_cls.assert_not_called()


@pytest.mark.anyio
async def test_ws_no_provider_falls_back_to_claude(mock_server_key):
    """No provider/api_key → fallback to server-stored Anthropic key + ClaudeService."""
    from starlette.testclient import TestClient

    with patch("routers.chat.ClaudeService") as mock_claude_cls:
        mock_claude = mock_claude_cls.return_value
        mock_claude.stream_response = _fake_stream(
            StreamEvent(type="text_delta", content="Server Claude"),
            StreamEvent(type="done"),
        )
        mock_claude.close = AsyncMock()

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({"content": "Hello"})

                events = []
                while True:
                    msg = ws.receive_json()
                    events.append(msg)
                    if msg["type"] == "done":
                        break

        mock_claude_cls.assert_called_once_with(api_key="sk-ant-server-key")


@pytest.mark.anyio
async def test_ws_google_provider_gets_gemini_prefix(mock_no_server_key):
    """Google provider should pass gemini/ prefix model to LLMService."""
    from starlette.testclient import TestClient

    with patch("routers.chat.LLMService") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.stream_response = _fake_stream(
            StreamEvent(type="text_delta", content="Gemini says hi"),
            StreamEvent(type="done"),
        )
        mock_llm.close = AsyncMock()

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({
                    "content": "Hello",
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "api_key": "goog-key",
                })

                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "done":
                        break

        # Verify LLMConfig was created with correct provider
        from services.llm_service import LLMConfig
        call_args = mock_llm_cls.call_args
        config_arg = call_args[0][0]  # first positional arg
        assert isinstance(config_arg, LLMConfig)
        assert config_arg.provider == "google"
        assert config_arg.model == "gemini-2.5-flash"


@pytest.mark.anyio
async def test_ws_no_key_no_server_key_returns_error(mock_no_server_key):
    """No client key and no server key → error event."""
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            ws.receive_json()  # session_start
            ws.send_json({"content": "Hello"})

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "API key not configured" in msg["content"]


@pytest.mark.anyio
async def test_ws_provider_model_passed_to_log_usage(mock_no_server_key):
    """Token usage logging should include provider and model."""
    from starlette.testclient import TestClient

    with patch("routers.chat.LLMService") as mock_llm_cls, \
         patch("routers.chat.log_usage") as mock_log:
        mock_llm = mock_llm_cls.return_value
        mock_llm.stream_response = _fake_stream(
            StreamEvent(type="text_delta", content="Hi"),
            StreamEvent(type="usage", input_tokens=100, output_tokens=50),
            StreamEvent(type="done"),
        )
        mock_llm.close = AsyncMock()

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({
                    "content": "Hello",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                })

                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "done":
                        break

        mock_log.assert_called_once_with(
            100, 50,
            model="gpt-4o",
            provider="openai",
        )


@pytest.mark.anyio
async def test_ws_connection_cache_reuses_same_provider(mock_no_server_key):
    """Same provider+key+model across messages should reuse the LLM instance."""
    from starlette.testclient import TestClient

    with patch("routers.chat.LLMService") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        mock_llm.stream_response = _fake_stream(
            StreamEvent(type="text_delta", content="Ok"),
            StreamEvent(type="done"),
        )
        mock_llm.close = AsyncMock()

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start

                # First message
                ws.send_json({
                    "content": "Hello",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                })
                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "done":
                        break

                # Second message — same provider
                ws.send_json({
                    "content": "Again",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "api_key": "sk-test",
                })
                while True:
                    msg = ws.receive_json()
                    if msg["type"] == "done":
                        break

        # LLMService should be created only once (cached)
        assert mock_llm_cls.call_count == 1
