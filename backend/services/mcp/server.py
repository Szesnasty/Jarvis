"""MCP Server — transport-agnostic tool registry, dispatch, and budget enforcement."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable

from services.mcp import mcp_logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MCPError(Exception):
    """Base for all MCP errors."""


class UnknownToolError(MCPError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown tool: {name}")
        self.tool_name = name


class ValidationError(MCPError):
    pass


class PrivacyBlockedError(MCPError):
    pass


# ---------------------------------------------------------------------------
# Cost classes
# ---------------------------------------------------------------------------


class CostClass(str, Enum):
    CHEAP = "cheap"
    MEDIUM = "medium"
    HEAVY = "heavy"


DEFAULT_BUDGETS = {
    CostClass.CHEAP: 1500,
    CostClass.MEDIUM: 4000,
    CostClass.HEAVY: 8000,
}


# ---------------------------------------------------------------------------
# Continuation cache (LRU, TTL)
# ---------------------------------------------------------------------------

_CONT_MAX = 50
_CONT_TTL = 300  # seconds

_continuation_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()


def _cont_put(payload: Any) -> str:
    token = secrets.token_urlsafe(16)
    now = time.monotonic()
    _continuation_cache[token] = (now, payload)
    # evict expired + over-cap
    expired = [k for k, (ts, _) in _continuation_cache.items() if now - ts > _CONT_TTL]
    for k in expired:
        _continuation_cache.pop(k, None)
    while len(_continuation_cache) > _CONT_MAX:
        _continuation_cache.popitem(last=False)
    return token


def _cont_get(token: str) -> Any | None:
    entry = _continuation_cache.pop(token, None)
    if entry is None:
        return None
    ts, payload = entry
    if time.monotonic() - ts > _CONT_TTL:
        return None
    return payload


# ---------------------------------------------------------------------------
# Token counting (lightweight, no API)
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English/mixed content."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Schema validation (minimal, no jsonschema dependency)
# ---------------------------------------------------------------------------


def _validate_args(args: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate tool arguments against the input_schema.

    Rejects unknown fields. Checks required fields and basic types.
    Intentionally simple — the heavy validation lives in the services.
    """
    if not isinstance(args, dict):
        raise ValidationError("Arguments must be a JSON object")

    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    if schema.get("additionalProperties") is False:
        extra = set(args) - set(props)
        if extra:
            raise ValidationError(f"Unknown fields: {', '.join(sorted(extra))}")

    for key in required:
        if key not in args:
            raise ValidationError(f"Missing required field: {key}")

    for key, value in args.items():
        if key not in props:
            continue
        spec = props[key]
        expected_type = spec.get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise ValidationError(f"Field '{key}' must be a string")
        if expected_type == "integer" and not isinstance(value, int):
            raise ValidationError(f"Field '{key}' must be an integer")
        if expected_type == "boolean" and not isinstance(value, bool):
            raise ValidationError(f"Field '{key}' must be a boolean")
        if expected_type == "string":
            max_len = spec.get("maxLength")
            if max_len and len(value) > max_len:
                raise ValidationError(f"Field '{key}' exceeds max length {max_len}")
            min_len = spec.get("minLength")
            if min_len and len(value) < min_len:
                raise ValidationError(f"Field '{key}' must be at least {min_len} chars")
            pattern = spec.get("pattern")
            if pattern and not re.match(pattern, value):
                raise ValidationError(f"Field '{key}' does not match pattern {pattern}")
            allowed = spec.get("enum")
            if allowed and value not in allowed:
                raise ValidationError(f"Field '{key}' must be one of {allowed}")
        if expected_type == "integer":
            mn = spec.get("minimum")
            if mn is not None and value < mn:
                raise ValidationError(f"Field '{key}' must be >= {mn}")
            mx = spec.get("maximum")
            if mx is not None and value > mx:
                raise ValidationError(f"Field '{key}' must be <= {mx}")


# ---------------------------------------------------------------------------
# Output budget enforcement
# ---------------------------------------------------------------------------


def _enforce_output_budget(result: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    """Truncate oversized results and add a continuation_token."""
    serialized = json.dumps(result, default=str)
    tokens = _estimate_tokens(serialized)
    if tokens <= max_tokens:
        return result

    # Try to truncate list-type results first
    if "results" in result and isinstance(result["results"], list):
        items = result["results"]
        kept: list[Any] = []
        running = _estimate_tokens(json.dumps({k: v for k, v in result.items() if k != "results"}, default=str))
        for item in items:
            item_cost = _estimate_tokens(json.dumps(item, default=str))
            if running + item_cost > max_tokens - 100:  # reserve room for meta
                break
            kept.append(item)
            running += item_cost

        remaining = items[len(kept):]
        truncated = {**result, "results": kept, "truncated": True}
        if remaining:
            truncated["continuation_token"] = _cont_put({"results": remaining})
        return truncated

    # For string-heavy results, truncate the largest string value
    if isinstance(result.get("content"), str):
        char_budget = max_tokens * 4  # reverse of token estimate
        content = result["content"]
        if len(content) > char_budget:
            remaining = content[char_budget:]
            truncated = {
                **result,
                "content": content[:char_budget],
                "truncated": True,
                "continuation_token": _cont_put({"content": remaining}),
            }
            return truncated

    return result


# ---------------------------------------------------------------------------
# Tool spec
# ---------------------------------------------------------------------------


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    cost_class: CostClass = CostClass.CHEAP
    max_output_tokens: int = 1500
    write: bool = False
    requires_external_network: bool = False


# ---------------------------------------------------------------------------
# MCP config
# ---------------------------------------------------------------------------


@dataclass
class MCPConfig:
    workspace_path: Path = field(default_factory=lambda: Path.home() / "Jarvis")
    allow_writes: bool = False
    tool_budgets: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


class JarvisMCPServer:
    """Transport-agnostic MCP server. Tool registry + dispatch + budget."""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "jarvis-mcp"
    SERVER_VERSION = "0.1.0"

    def __init__(self, tools: list[ToolSpec], config: MCPConfig | None = None) -> None:
        self._all_tools = {t.name: t for t in tools}
        self.config = config or MCPConfig()

    # -- Protocol methods ---------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": self.SERVER_NAME,
                "version": self.SERVER_VERSION,
            },
        }

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for t in self._all_tools.values():
            if t.write and not self.config.allow_writes:
                continue
            tools.append(
                {
                    "name": t.name,
                    "description": t.description[:400],
                    "inputSchema": t.input_schema,
                }
            )
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        client_id: str = "unknown",
    ) -> dict[str, Any]:
        arguments = arguments or {}

        # Built-in continuation tool
        if name == "jarvis_continue":
            return self._handle_continue(arguments)

        tool = self._all_tools.get(name)
        if tool is None:
            raise UnknownToolError(name)

        # Hide write tools when writes disabled
        if tool.write and not self.config.allow_writes:
            raise UnknownToolError(name)

        # Privacy gate
        if tool.requires_external_network:
            self._check_privacy(name)

        # Validate
        _validate_args(arguments, tool.input_schema)

        # Execute with logging
        async with mcp_logging.log_call(
            self.config.workspace_path,
            tool=name,
            args=arguments,
            client_id=client_id,
        ) as log_entry:
            raw = await tool.handler(arguments)

        # Budget enforcement
        budget = self.config.tool_budgets.get(name, tool.max_output_tokens)
        result = _enforce_output_budget(raw, budget)

        # Record output tokens in log
        output_tokens = _estimate_tokens(json.dumps(result, default=str))
        log_entry["output_tokens"] = output_tokens

        return result

    def _handle_continue(self, args: dict[str, Any]) -> dict[str, Any]:
        token = args.get("continuation_token", "")
        if not isinstance(token, str) or not token:
            raise ValidationError("continuation_token is required")
        payload = _cont_get(token)
        if payload is None:
            raise MCPError("Continuation token expired or invalid")
        return payload

    @staticmethod
    def _check_privacy(tool_name: str) -> None:
        try:
            from services.privacy import is_offline_mode, web_search_enabled

            if is_offline_mode() or not web_search_enabled():
                raise PrivacyBlockedError(f"{tool_name} blocked by privacy settings")
        except ImportError:
            pass  # privacy module not present on this branch — allow
