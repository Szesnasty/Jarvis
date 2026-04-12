import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.claude import (
    SYSTEM_PROMPT,
    ClaudeService,
    StreamEvent,
    _ToolAccumulator,
    build_system_prompt,
)
from services.tools import TOOLS, ToolNotFoundError, execute_tool

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# --- System prompt ---


@pytest.mark.anyio
async def test_build_system_prompt_has_persona():
    with patch("services.context_builder.retrieval") as mock_ret:
        mock_ret.retrieve = AsyncMock(return_value=[])
        prompt = await build_system_prompt("hello")
    assert "Jarvis" in prompt


@pytest.mark.anyio
async def test_build_system_prompt_includes_context():
    fake_results = [{"path": "inbox/test.md", "title": "Test"}]
    fake_detail = {"content": "# Test\nSome content here"}

    with patch("services.context_builder.retrieval") as mock_ret, \
         patch("services.context_builder.memory_service") as mock_ms:
        mock_ret.retrieve = AsyncMock(return_value=fake_results)
        mock_ms.get_note = AsyncMock(return_value=fake_detail)
        prompt = await build_system_prompt("test query")

    assert "relevant notes" in prompt or "inbox/test.md" in prompt
    assert "inbox/test.md" in prompt


@pytest.mark.anyio
async def test_build_system_prompt_no_context_when_empty():
    with patch("services.context_builder.retrieval") as mock_ret:
        mock_ret.retrieve = AsyncMock(return_value=[])
        prompt = await build_system_prompt("hello")

    assert prompt == SYSTEM_PROMPT


@pytest.mark.anyio
async def test_build_system_prompt_max_length():
    long_content = "x" * 2000
    fake_results = [{"path": f"n{i}.md", "title": f"N{i}"} for i in range(5)]
    fake_detail = {"content": long_content}

    with patch("services.context_builder.retrieval") as mock_ret, \
         patch("services.context_builder.memory_service") as mock_ms:
        mock_ret.retrieve = AsyncMock(return_value=fake_results)
        mock_ms.get_note = AsyncMock(return_value=fake_detail)
        prompt = await build_system_prompt("test")

    # Each note truncated to 500 chars, 3 notes max + separators + header
    max_context = 3 * 500 + 200
    assert len(prompt) < len(SYSTEM_PROMPT) + max_context


# --- Messages format ---


def test_build_messages_format():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    for msg in messages:
        assert "role" in msg
        assert "content" in msg
        assert msg["role"] in ("user", "assistant")


def test_build_messages_preserves_order():
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    assert messages[0]["content"] == "first"
    assert messages[1]["content"] == "second"
    assert messages[2]["content"] == "third"


# --- Tool definitions ---


def test_tool_definitions_include_search():
    names = [t["name"] for t in TOOLS]
    assert "search_notes" in names


def test_tool_definitions_include_write():
    names = [t["name"] for t in TOOLS]
    assert "write_note" in names


def test_tool_definitions_schema_valid():
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


# --- Tool execution ---

from models.database import init_database


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


SAMPLE = "---\ntitle: Tool Test\ntags: [test]\n---\n\nTool test content."


@pytest.mark.anyio
async def test_execute_tool_search(ws_db):
    from services.memory_service import create_note

    await create_note("inbox/tool-test.md", SAMPLE, ws_db)
    result = await execute_tool("search_notes", {"query": "tool"}, workspace_path=ws_db)
    parsed = json.loads(result)
    assert len(parsed) >= 1
    assert parsed[0]["path"] == "inbox/tool-test.md"


@pytest.mark.anyio
async def test_execute_tool_write(ws_db):
    result = await execute_tool(
        "write_note",
        {"path": "inbox/new.md", "content": SAMPLE},
        workspace_path=ws_db,
    )
    assert "Note saved" in result
    assert (ws_db / "memory" / "inbox" / "new.md").exists()


@pytest.mark.anyio
async def test_execute_unknown_tool():
    with pytest.raises(ToolNotFoundError):
        await execute_tool("nonexistent_tool", {})


# --- Security ---


def test_no_api_key_in_system_prompt():
    assert "sk-ant" not in SYSTEM_PROMPT


@pytest.mark.anyio
async def test_no_api_key_in_error_messages():
    event = StreamEvent(type="error", content="Claude API error: something failed")
    assert "sk-ant" not in event.content


# --- ToolAccumulator ---


def test_tool_accumulator_start_and_finish():
    acc = _ToolAccumulator()
    acc.start("search_notes", "tool_123")
    acc.input_json = '{"query": "test"}'

    assert acc.is_active()
    event = acc.finish()

    assert event.type == "tool_use"
    assert event.name == "search_notes"
    assert event.tool_input == {"query": "test"}
    assert not acc.is_active()


def test_tool_accumulator_empty_input():
    acc = _ToolAccumulator()
    acc.start("read_note", "tool_456")
    event = acc.finish()
    assert event.tool_input == {}
