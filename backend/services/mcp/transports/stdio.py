"""MCP stdio transport — reads JSON-RPC from stdin, writes to stdout."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, TextIO

from services.mcp.server import (
    JarvisMCPServer,
    MCPError,
    UnknownToolError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class StdioTransport:
    """JSON-RPC 2.0 over stdin/stdout for the MCP protocol."""

    def __init__(
        self,
        server: JarvisMCPServer,
        *,
        reader: TextIO | None = None,
        writer: TextIO | None = None,
    ) -> None:
        self._server = server
        self._reader = reader or sys.stdin
        self._writer = writer or sys.stdout
        self._initialized = False

    async def run(self) -> None:
        """Read lines from stdin and dispatch JSON-RPC messages."""
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, self._reader.readline)
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._send_error(None, -32700, "Parse error")
                continue
            await self._dispatch(msg)

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        msg_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {})

        # Notifications (no id) — we only handle initialized
        if msg_id is None:
            if method == "notifications/initialized":
                self._initialized = True
            return

        try:
            if method == "initialize":
                result = self._server.initialize()
                self._send_result(msg_id, result)

            elif method == "tools/list":
                tools = self._server.list_tools()
                self._send_result(msg_id, {"tools": tools})

            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = await self._server.call_tool(
                    name, arguments, client_id="stdio"
                )
                self._send_result(
                    msg_id,
                    {
                        "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                        "isError": False,
                    },
                )

            elif method == "ping":
                self._send_result(msg_id, {})

            else:
                self._send_error(msg_id, -32601, f"Method not found: {method}")

        except UnknownToolError as exc:
            self._send_result(
                msg_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            )
        except ValidationError as exc:
            self._send_result(
                msg_id,
                {
                    "content": [{"type": "text", "text": f"Validation error: {exc}"}],
                    "isError": True,
                },
            )
        except MCPError as exc:
            self._send_result(
                msg_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            )
        except Exception as exc:
            logger.exception("Unexpected error in MCP dispatch")
            self._send_error(msg_id, -32603, f"Internal error: {type(exc).__name__}")

    def _send_result(self, msg_id: Any, result: Any) -> None:
        self._write({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def _send_error(self, msg_id: Any, code: int, message: str) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": code, "message": message},
            }
        )

    def _write(self, msg: dict[str, Any]) -> None:
        line = json.dumps(msg, default=str)
        self._writer.write(line + "\n")
        self._writer.flush()
