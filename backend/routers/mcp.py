"""MCP server info endpoint — read-only.

The MCP server itself is a standalone CLI (`jarvis-mcp`) launched by
the client (Cursor, Claude Desktop, VS Code, etc.) via stdio.

This router only reports configuration helpers used by the Settings UI.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from config import get_settings
from mcp_server.app import build_app
from mcp_server.middleware.audit import get_stats

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class McpInfoResponse(BaseModel):
    cli_on_path: bool
    cli_path: str | None
    cli_command: str
    workspace_path: str
    backend_dir: str
    tool_count: int
    write_tool_count: int
    audit_log_path: str
    calls_today: int
    last_call: str | None
    top_tool: str | None


@router.get("/info", response_model=McpInfoResponse)
async def mcp_info() -> McpInfoResponse:
    ws = get_settings().workspace_path
    backend_dir = Path(__file__).resolve().parent.parent
    cli_path = shutil.which("jarvis-mcp")

    read_app = build_app(ws, allow_writes=False)
    write_app = build_app(ws, allow_writes=True)
    read_count = len(await read_app.list_tools())
    write_count = len(await write_app.list_tools()) - read_count

    stats = get_stats(ws)

    return McpInfoResponse(
        cli_on_path=cli_path is not None,
        cli_path=cli_path,
        cli_command="jarvis-mcp" if cli_path else f"{backend_dir}/.venv/bin/jarvis-mcp",
        workspace_path=str(ws),
        backend_dir=str(backend_dir),
        tool_count=read_count,
        write_tool_count=write_count,
        audit_log_path=str(ws / "app" / "logs" / "mcp.jsonl"),
        calls_today=stats.get("calls_today", 0),
        last_call=stats.get("last_call"),
        top_tool=stats.get("top_tool"),
    )
