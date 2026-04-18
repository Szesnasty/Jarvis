"""Tool registry — exposes all Jarvis MCP tools to a FastMCP instance."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import (
    continuation,
    graph,
    jira,
    meta,
    notes,
    search,
    sessions,
    writes,
)


def register_all(mcp: FastMCP, *, workspace: Path, allow_writes: bool = False) -> None:
    """Register every Jarvis tool with the given FastMCP instance."""
    search.register(mcp, workspace=workspace)
    notes.register(mcp, workspace=workspace)
    graph.register(mcp, workspace=workspace)
    jira.register(mcp, workspace=workspace)
    sessions.register(mcp, workspace=workspace)
    meta.register(mcp, workspace=workspace)
    continuation.register(mcp)
    if allow_writes:
        writes.register(mcp, workspace=workspace)
