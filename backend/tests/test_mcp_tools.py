"""Tests for MCP server core: tool registry, dispatch, budget enforcement, auth."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from services.mcp.server import (
    CostClass,
    JarvisMCPServer,
    MCPConfig,
    MCPError,
    ToolSpec,
    UnknownToolError,
    ValidationError,
    _cont_get,
    _cont_put,
    _enforce_output_budget,
    _estimate_tokens,
    _validate_args,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_workspace(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "logs").mkdir()
    (tmp_path / "memory").mkdir()
    return tmp_path


@pytest.fixture
def dummy_handler():
    async def handler(args):
        return {"message": "ok", "echo": args}

    return handler


@pytest.fixture
def dummy_tools(dummy_handler):
    return [
        ToolSpec(
            name="test_read",
            description="A test read tool",
            input_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 100},
                },
                "additionalProperties": False,
            },
            handler=dummy_handler,
            cost_class=CostClass.CHEAP,
            max_output_tokens=1000,
        ),
        ToolSpec(
            name="test_write",
            description="A test write tool",
            input_schema={
                "type": "object",
                "required": ["data"],
                "properties": {
                    "data": {"type": "string", "maxLength": 500},
                },
                "additionalProperties": False,
            },
            handler=dummy_handler,
            cost_class=CostClass.CHEAP,
            max_output_tokens=200,
            write=True,
        ),
        ToolSpec(
            name="test_network",
            description="A test tool requiring network",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=dummy_handler,
            cost_class=CostClass.CHEAP,
            max_output_tokens=500,
            requires_external_network=True,
        ),
    ]


@pytest.fixture
def server_no_writes(dummy_tools, tmp_workspace):
    config = MCPConfig(workspace_path=tmp_workspace, allow_writes=False)
    return JarvisMCPServer(dummy_tools, config)


@pytest.fixture
def server_with_writes(dummy_tools, tmp_workspace):
    config = MCPConfig(workspace_path=tmp_workspace, allow_writes=True)
    return JarvisMCPServer(dummy_tools, config)


# ---------------------------------------------------------------------------
# Tests: Tool listing
# ---------------------------------------------------------------------------


class TestToolListing:
    def test_list_tools_hides_writes_when_disabled(self, server_no_writes):
        tools = server_no_writes.list_tools()
        names = [t["name"] for t in tools]
        assert "test_read" in names
        assert "test_write" not in names
        assert "test_network" in names

    def test_list_tools_shows_writes_when_enabled(self, server_with_writes):
        tools = server_with_writes.list_tools()
        names = [t["name"] for t in tools]
        assert "test_read" in names
        assert "test_write" in names

    def test_tool_descriptions_capped_at_400(self, server_with_writes):
        for t in server_with_writes.list_tools():
            assert len(t["description"]) <= 400


class TestInitialize:
    def test_initialize_returns_capabilities(self, server_no_writes):
        result = server_no_writes.initialize()
        assert "protocolVersion" in result
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "jarvis-mcp"


# ---------------------------------------------------------------------------
# Tests: Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_rejects_extra_fields(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "additionalProperties": False,
        }
        with pytest.raises(ValidationError, match="Unknown fields"):
            _validate_args({"a": "ok", "b": "extra"}, schema)

    def test_rejects_missing_required(self):
        schema = {
            "type": "object",
            "required": ["x"],
            "properties": {"x": {"type": "string"}},
        }
        with pytest.raises(ValidationError, match="Missing required"):
            _validate_args({}, schema)

    def test_rejects_wrong_type_string(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        with pytest.raises(ValidationError, match="must be a string"):
            _validate_args({"x": 123}, schema)

    def test_rejects_wrong_type_integer(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        with pytest.raises(ValidationError, match="must be an integer"):
            _validate_args({"x": "hi"}, schema)

    def test_rejects_string_too_long(self):
        schema = {"type": "object", "properties": {"x": {"type": "string", "maxLength": 5}}}
        with pytest.raises(ValidationError, match="max length"):
            _validate_args({"x": "toolong"}, schema)

    def test_rejects_string_too_short(self):
        schema = {"type": "object", "properties": {"x": {"type": "string", "minLength": 3}}}
        with pytest.raises(ValidationError, match="at least"):
            _validate_args({"x": "ab"}, schema)

    def test_rejects_bad_enum(self):
        schema = {"type": "object", "properties": {"x": {"type": "string", "enum": ["a", "b"]}}}
        with pytest.raises(ValidationError, match="must be one of"):
            _validate_args({"x": "c"}, schema)

    def test_rejects_pattern_mismatch(self):
        schema = {"type": "object", "properties": {"x": {"type": "string", "pattern": "^[A-Z]+$"}}}
        with pytest.raises(ValidationError, match="pattern"):
            _validate_args({"x": "abc"}, schema)

    def test_rejects_integer_out_of_range(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer", "minimum": 1, "maximum": 10}}}
        with pytest.raises(ValidationError):
            _validate_args({"x": 11}, schema)
        with pytest.raises(ValidationError):
            _validate_args({"x": 0}, schema)

    def test_accepts_valid_args(self):
        schema = {
            "type": "object",
            "required": ["q"],
            "properties": {
                "q": {"type": "string", "minLength": 1, "maxLength": 50},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "additionalProperties": False,
        }
        _validate_args({"q": "hello", "limit": 5}, schema)  # no exception

    def test_rejects_non_dict(self):
        with pytest.raises(ValidationError, match="JSON object"):
            _validate_args("not a dict", {})  # type: ignore


# ---------------------------------------------------------------------------
# Tests: Tool dispatch
# ---------------------------------------------------------------------------


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_call_read_tool_happy_path(self, server_no_writes):
        result = await server_no_writes.call_tool("test_read", {"query": "hello"})
        assert result["message"] == "ok"
        assert result["echo"]["query"] == "hello"

    @pytest.mark.asyncio
    async def test_call_unknown_tool_raises(self, server_no_writes):
        with pytest.raises(UnknownToolError):
            await server_no_writes.call_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_call_write_tool_when_disabled_raises(self, server_no_writes):
        with pytest.raises(UnknownToolError):
            await server_no_writes.call_tool("test_write", {"data": "hi"})

    @pytest.mark.asyncio
    async def test_call_write_tool_when_enabled_works(self, server_with_writes):
        result = await server_with_writes.call_tool("test_write", {"data": "hi"})
        assert result["message"] == "ok"

    @pytest.mark.asyncio
    async def test_invalid_args_rejected_before_handler(self, server_no_writes):
        with pytest.raises(ValidationError):
            await server_no_writes.call_tool("test_read", {"query": 123})

    @pytest.mark.asyncio
    async def test_extra_fields_rejected(self, server_no_writes):
        with pytest.raises(ValidationError, match="Unknown fields"):
            await server_no_writes.call_tool("test_read", {"query": "hi", "evil": "inject"})


# ---------------------------------------------------------------------------
# Tests: Cost-class enforcement & continuation
# ---------------------------------------------------------------------------


class TestBudgetEnforcement:
    def test_small_result_passes_through(self):
        result = {"message": "short"}
        enforced = _enforce_output_budget(result, 1000)
        assert enforced == result
        assert "truncated" not in enforced

    def test_large_list_truncated_with_continuation(self):
        items = [{"text": f"item {i} " * 100} for i in range(50)]
        result = {"results": items}
        enforced = _enforce_output_budget(result, 500)
        assert enforced.get("truncated") is True
        assert "continuation_token" in enforced
        assert len(enforced["results"]) < 50

    def test_continuation_token_retrievable(self):
        items = [{"text": f"item {i} " * 100} for i in range(50)]
        result = {"results": items}
        enforced = _enforce_output_budget(result, 500)
        token = enforced["continuation_token"]
        remaining = _cont_get(token)
        assert remaining is not None
        assert "results" in remaining
        assert len(remaining["results"]) > 0

    def test_continuation_token_single_use(self):
        token = _cont_put({"data": "test"})
        assert _cont_get(token) is not None
        assert _cont_get(token) is None  # second call returns None

    def test_content_string_truncation(self):
        result = {"content": "x" * 100000}
        enforced = _enforce_output_budget(result, 500)
        assert enforced.get("truncated") is True
        assert len(enforced["content"]) < 100000

    def test_token_estimation(self):
        assert _estimate_tokens("") == 1
        assert _estimate_tokens("hello world") > 0
        # ~4 chars per token
        assert abs(_estimate_tokens("a" * 400) - 100) < 10


class TestContinueBuiltIn:
    @pytest.mark.asyncio
    async def test_jarvis_continue_returns_remaining(self, server_no_writes):
        token = _cont_put({"results": [{"a": 1}]})
        result = await server_no_writes.call_tool("jarvis_continue", {"continuation_token": token})
        assert result["results"] == [{"a": 1}]

    @pytest.mark.asyncio
    async def test_jarvis_continue_expired_token(self, server_no_writes):
        with pytest.raises(MCPError, match="expired"):
            await server_no_writes.call_tool("jarvis_continue", {"continuation_token": "nonexistent"})

    @pytest.mark.asyncio
    async def test_jarvis_continue_missing_token(self, server_no_writes):
        with pytest.raises(ValidationError):
            await server_no_writes.call_tool("jarvis_continue", {})


# ---------------------------------------------------------------------------
# Tests: Auth
# ---------------------------------------------------------------------------


class TestAuth:
    def test_ensure_token_creates_file(self, tmp_workspace):
        from services.mcp.auth import ensure_token

        token = ensure_token(tmp_workspace)
        assert len(token) > 20
        token_file = tmp_workspace / "app" / "mcp_token"
        assert token_file.exists()
        assert oct(token_file.stat().st_mode)[-3:] == "600"

    def test_ensure_token_idempotent(self, tmp_workspace):
        from services.mcp.auth import ensure_token

        t1 = ensure_token(tmp_workspace)
        t2 = ensure_token(tmp_workspace)
        assert t1 == t2

    def test_regenerate_token_changes_value(self, tmp_workspace):
        from services.mcp.auth import ensure_token, regenerate_token

        t1 = ensure_token(tmp_workspace)
        t2 = regenerate_token(tmp_workspace)
        assert t1 != t2

    def test_verify_bearer_correct(self):
        from services.mcp.auth import verify_bearer

        assert verify_bearer("Bearer abc123", "abc123") is True

    def test_verify_bearer_wrong(self):
        from services.mcp.auth import verify_bearer

        assert verify_bearer("Bearer wrong", "abc123") is False

    def test_verify_bearer_missing(self):
        from services.mcp.auth import verify_bearer

        assert verify_bearer(None, "abc123") is False
        assert verify_bearer("", "abc123") is False

    def test_verify_bearer_bad_scheme(self):
        from services.mcp.auth import verify_bearer

        assert verify_bearer("Basic abc123", "abc123") is False


# ---------------------------------------------------------------------------
# Tests: Logging
# ---------------------------------------------------------------------------


class TestLogging:
    @pytest.mark.asyncio
    async def test_log_call_writes_jsonl(self, tmp_workspace):
        from services.mcp.mcp_logging import log_call, get_stats

        async with log_call(tmp_workspace, tool="test_tool", args={"q": "hi"}) as entry:
            entry["output_tokens"] = 42

        stats = get_stats(tmp_workspace)
        assert stats["calls_today"] >= 1
        assert stats["top_tool"] == "test_tool"

    def test_hash_args_deterministic(self):
        from services.mcp.mcp_logging import hash_args

        h1 = hash_args({"a": 1, "b": 2})
        h2 = hash_args({"b": 2, "a": 1})
        assert h1 == h2
        assert len(h1) == 16


# ---------------------------------------------------------------------------
# Tests: Privacy
# ---------------------------------------------------------------------------


class TestPrivacy:
    @pytest.mark.asyncio
    async def test_network_tool_blocked_when_offline(self, dummy_tools, tmp_workspace):
        from services.mcp.server import PrivacyBlockedError

        config = MCPConfig(workspace_path=tmp_workspace, allow_writes=True)
        server = JarvisMCPServer(dummy_tools, config)

        with patch("services.mcp.server.JarvisMCPServer._check_privacy") as mock:
            mock.side_effect = PrivacyBlockedError("blocked")
            with pytest.raises(PrivacyBlockedError):
                await server.call_tool("test_network", {})

    @pytest.mark.asyncio
    async def test_read_tools_work_regardless_of_privacy(self, server_no_writes):
        # Read tools don't require network — should always work
        result = await server_no_writes.call_tool("test_read", {"query": "test"})
        assert result["message"] == "ok"


# ---------------------------------------------------------------------------
# Tests: Stdio transport
# ---------------------------------------------------------------------------


class TestStdioTransport:
    @pytest.mark.asyncio
    async def test_initialize_handshake(self, server_no_writes):
        import io
        from services.mcp.transports.stdio import StdioTransport

        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        reader = io.StringIO(request + "\n")
        writer = io.StringIO()

        transport = StdioTransport(server_no_writes, reader=reader, writer=writer)
        await transport.run()

        writer.seek(0)
        response = json.loads(writer.readline())
        assert response["id"] == 1
        assert "protocolVersion" in response["result"]

    @pytest.mark.asyncio
    async def test_tools_list(self, server_no_writes):
        import io
        from services.mcp.transports.stdio import StdioTransport

        request = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        reader = io.StringIO(request + "\n")
        writer = io.StringIO()

        transport = StdioTransport(server_no_writes, reader=reader, writer=writer)
        await transport.run()

        writer.seek(0)
        response = json.loads(writer.readline())
        tools = response["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "test_read" in names

    @pytest.mark.asyncio
    async def test_tool_call(self, server_no_writes):
        import io
        from services.mcp.transports.stdio import StdioTransport

        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "test_read", "arguments": {"query": "hello"}},
        })
        reader = io.StringIO(request + "\n")
        writer = io.StringIO()

        transport = StdioTransport(server_no_writes, reader=reader, writer=writer)
        await transport.run()

        writer.seek(0)
        response = json.loads(writer.readline())
        assert response["result"]["isError"] is False
        content = json.loads(response["result"]["content"][0]["text"])
        assert content["echo"]["query"] == "hello"

    @pytest.mark.asyncio
    async def test_unknown_method(self, server_no_writes):
        import io
        from services.mcp.transports.stdio import StdioTransport

        request = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "unknown/method", "params": {}})
        reader = io.StringIO(request + "\n")
        writer = io.StringIO()

        transport = StdioTransport(server_no_writes, reader=reader, writer=writer)
        await transport.run()

        writer.seek(0)
        response = json.loads(writer.readline())
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_invalid_json(self, server_no_writes):
        import io
        from services.mcp.transports.stdio import StdioTransport

        reader = io.StringIO("not json\n")
        writer = io.StringIO()

        transport = StdioTransport(server_no_writes, reader=reader, writer=writer)
        await transport.run()

        writer.seek(0)
        response = json.loads(writer.readline())
        assert "error" in response
        assert response["error"]["code"] == -32700


# ---------------------------------------------------------------------------
# Tests: Full tool catalogue (from build_tools)
# ---------------------------------------------------------------------------


class TestToolCatalogue:
    def test_read_tool_count(self):
        from services.mcp.tools import build_tools

        tools = build_tools()
        read_tools = [t for t in tools if not t.write]
        assert len(read_tools) >= 15  # spec says at least 15

    def test_write_tool_count(self):
        from services.mcp.tools import build_tools

        tools = build_tools()
        write_tools = [t for t in tools if t.write]
        assert len(write_tools) == 3

    def test_all_tools_have_valid_schema(self):
        from services.mcp.tools import build_tools

        tools = build_tools()
        for t in tools:
            assert "type" in t.input_schema
            assert t.input_schema["type"] == "object"
            assert "properties" in t.input_schema

    def test_all_tools_have_cost_class(self):
        from services.mcp.tools import build_tools

        tools = build_tools()
        for t in tools:
            assert isinstance(t.cost_class, CostClass)
            assert t.max_output_tokens > 0

    def test_namespace_coverage(self):
        from services.mcp.tools import build_tools

        tools = build_tools()
        names = [t.name for t in tools]
        # All 6 namespaces must be represented
        assert any(n.startswith("jarvis_search_") for n in names)
        assert any(n.startswith("jarvis_note_") for n in names)
        assert any(n.startswith("jarvis_graph_") for n in names)
        assert any(n.startswith("jarvis_jira_") for n in names)
        assert any(n.startswith("jarvis_session_") for n in names)
        # Meta tools use varied prefixes
        assert "jarvis_get_preferences" in names
        assert "jarvis_workspace_stats" in names
