"""FastMCP application factory."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import register_all


def build_app(workspace: Path, *, allow_writes: bool = False) -> FastMCP:
    mcp = FastMCP("jarvis")
    register_all(mcp, workspace=workspace, allow_writes=allow_writes)
    return mcp
