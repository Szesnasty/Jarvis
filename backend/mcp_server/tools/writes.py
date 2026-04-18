"""Opt-in write tools — only registered when --allow-writes is set."""

from __future__ import annotations

import asyncio
import json as _json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_save_preference",
        description="Persist a user preference Jarvis will recall in every future session.",
    )
    @audit("jarvis_save_preference", ws)
    @enforce_budget(max_tokens=200)
    async def jarvis_save_preference(category: str, rule: str) -> dict:
        from services.preference_service import save_preference

        key = f"{category}.{rule[:50]}"
        await asyncio.to_thread(save_preference, key, rule, workspace_path=workspace)
        return {"saved": True, "key": key}

    @mcp.tool(
        name="jarvis_append_note",
        description="Append a block to an existing note (never creates new notes).",
    )
    @audit("jarvis_append_note", ws)
    @enforce_budget(max_tokens=200)
    async def jarvis_append_note(path: str, text: str) -> dict:
        from services.memory_service import NoteNotFoundError, append_note

        try:
            result = await append_note(path, text, workspace_path=workspace)
            return {"appended": True, "path": result.get("path", path)}
        except NoteNotFoundError:
            return {"error": f"Note '{path}' not found. Create it in Jarvis UI first."}

    @mcp.tool(
        name="jarvis_summarize_and_save",
        description="Summarize content and optionally save to a daily note.",
    )
    @audit("jarvis_summarize_and_save", ws)
    @enforce_budget(max_tokens=2000)
    async def jarvis_summarize_and_save(
        content: str,
        title: str = "summary",
        save: bool = True,
    ) -> dict:
        from services.tools.executor import execute_tool

        result_str = await execute_tool(
            "summarize_context",
            {"content": content, "title": title, "save": save},
            workspace_path=workspace,
        )
        try:
            return _json.loads(result_str)
        except (ValueError, TypeError):
            return {"content": result_str, "saved": False}
