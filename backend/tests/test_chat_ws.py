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
    """Prevent tests from writing session files to the real workspace."""
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
    for d in ["app", "app/sessions", "memory", "memory/inbox",
              "memory/preferences", "graph"]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)


def _fake_stream(*events: StreamEvent):
    """Create an AsyncMock that yields StreamEvents."""

    async def _gen(**kwargs):
        for e in events:
            yield e

    return _gen


def _fake_tool_then_text(tool_event: StreamEvent, follow_up_text: str = ""):
    """First call yields tool_use, subsequent calls yield text (for follow-up)."""
    call_count = 0

    async def _gen(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield tool_event
        elif follow_up_text:
            yield StreamEvent(type="text_delta", content=follow_up_text)

    return _gen


@pytest.fixture
def mock_api_key():
    with patch("routers.chat.get_api_key", return_value="sk-ant-test-key"):
        yield


@pytest.fixture
def mock_claude_stream():
    """Patch ClaudeService.stream_response to return fake events."""
    with patch("routers.chat.ClaudeService") as mock_cls:
        instance = mock_cls.return_value
        yield instance


# --- WebSocket tests ---


@pytest.mark.anyio
async def test_ws_connect_succeeds(mock_api_key):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with ac.stream("GET", "/api/chat/ws") as _:
            pass
    # If we get here without exception, the WS route exists.
    # Full WS testing below uses starlette testclient.


@pytest.mark.anyio
async def test_ws_connect_returns_session_id(mock_api_key):
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "session_start"
            assert "session_id" in data


@pytest.mark.anyio
async def test_ws_send_message_receives_chunks(mock_api_key, mock_claude_stream):
    mock_claude_stream.stream_response = _fake_stream(
        StreamEvent(type="text_delta", content="Hello "),
        StreamEvent(type="text_delta", content="world"),
    )

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            ws.receive_json()  # session_start
            ws.send_json({"content": "Hi"})

            chunks = []
            while True:
                msg = ws.receive_json()
                if msg["type"] == "done":
                    break
                chunks.append(msg)

            text_chunks = [c for c in chunks if c["type"] == "text_delta"]
            assert len(text_chunks) == 2
            assert text_chunks[0]["content"] == "Hello "


@pytest.mark.anyio
async def test_ws_chunks_form_complete_response(mock_api_key, mock_claude_stream):
    mock_claude_stream.stream_response = _fake_stream(
        StreamEvent(type="text_delta", content="Hello "),
        StreamEvent(type="text_delta", content="world!"),
    )

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            ws.receive_json()  # session_start
            ws.send_json({"content": "Hi"})

            full_text = ""
            while True:
                msg = ws.receive_json()
                if msg["type"] == "done":
                    break
                if msg["type"] == "text_delta":
                    full_text += msg["content"]

            assert full_text == "Hello world!"


@pytest.mark.anyio
async def test_ws_tool_use_event(mock_api_key, mock_claude_stream):
    mock_claude_stream.stream_response = _fake_tool_then_text(
        StreamEvent(
            type="tool_use",
            name="search_notes",
            tool_input={"query": "test"},
            tool_use_id="tool_1",
        ),
    )

    with patch("routers.chat.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = '[{"path": "test.md"}]'

        from starlette.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({"content": "search for test"})

                events = []
                while True:
                    msg = ws.receive_json()
                    events.append(msg)
                    if msg["type"] == "done":
                        break

                tool_events = [e for e in events if e["type"] == "tool_use"]
                assert len(tool_events) == 1
                assert tool_events[0]["name"] == "search_notes"


@pytest.mark.anyio
async def test_ws_tool_result_event(mock_api_key, mock_claude_stream):
    mock_claude_stream.stream_response = _fake_tool_then_text(
        StreamEvent(
            type="tool_use",
            name="search_notes",
            tool_input={"query": "test"},
            tool_use_id="tool_1",
        ),
    )

    with patch("routers.chat.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = '[{"path": "test.md"}]'

        from starlette.testclient import TestClient

        with TestClient(app) as client:
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.receive_json()  # session_start
                ws.send_json({"content": "search"})

                events = []
                while True:
                    msg = ws.receive_json()
                    events.append(msg)
                    if msg["type"] == "done":
                        break

                result_events = [e for e in events if e["type"] == "tool_result"]
                assert len(result_events) == 1
                assert "test.md" in result_events[0]["content"]


@pytest.mark.anyio
async def test_ws_session_history_grows(mock_api_key, mock_claude_stream):
    call_count = 0

    async def _stream(**kwargs):
        nonlocal call_count
        call_count += 1
        yield StreamEvent(type="text_delta", content=f"Reply {call_count}")

    mock_claude_stream.stream_response = _stream

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            start = ws.receive_json()
            sid = start["session_id"]

            ws.send_json({"content": "first"})
            while ws.receive_json()["type"] != "done":
                pass

            ws.send_json({"content": "second"})
            while ws.receive_json()["type"] != "done":
                pass

            from services.session_service import get_messages

            msgs = get_messages(sid)
            assert len(msgs) == 4  # user, assistant, user, assistant


@pytest.mark.anyio
async def test_ws_invalid_json(mock_api_key):
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            ws.receive_json()  # session_start
            ws.send_text("not json at all")
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Invalid JSON" in msg["content"]


@pytest.mark.anyio
async def test_ws_empty_message(mock_api_key):
    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            ws.receive_json()  # session_start
            ws.send_json({"content": ""})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "required" in msg["content"].lower()


@pytest.mark.anyio
async def test_ws_disconnect_cleanup(mock_api_key, mock_claude_stream):
    mock_claude_stream.stream_response = _fake_stream(
        StreamEvent(type="text_delta", content="hi"),
    )

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        with client.websocket_connect("/api/chat/ws") as ws:
            start = ws.receive_json()
            sid = start["session_id"]

    # After disconnect, session is kept for potential resume (not deleted)
    from services.session_service import get_session

    session = get_session(sid)
    assert session is not None
    assert session["id"] == sid
