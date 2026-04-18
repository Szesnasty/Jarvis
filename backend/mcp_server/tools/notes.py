"""Notes tools — read, list, outline."""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_note_read",
        description=(
            "Read a single note by workspace-relative path. "
            "Returns frontmatter + body (truncated to max_chars)."
        ),
    )
    @audit("jarvis_note_read", ws)
    @enforce_budget(max_tokens=4000)
    async def jarvis_note_read(
        path: str,
        max_chars: int = 8000,
        include_frontmatter: bool = True,
    ) -> dict:
        from services.memory_service import get_note

        note = await get_note(path, workspace_path=workspace)
        content = note.get("content", "")
        if len(content) > max_chars:
            content = content[:max_chars]

        result: dict = {
            "path": note.get("path", path),
            "title": note.get("title", ""),
            "content": content,
        }
        if include_frontmatter and note.get("frontmatter"):
            result["frontmatter"] = note["frontmatter"]
        return result

    @mcp.tool(
        name="jarvis_note_list",
        description=(
            "List notes in a folder. Returns paths + titles only — cheap directory listing. "
            "Optional filters: tag, modified_after (ISO date)."
        ),
    )
    @audit("jarvis_note_list", ws)
    @enforce_budget(max_tokens=2000)
    async def jarvis_note_list(
        folder: str = "",
        tag: str | None = None,
        modified_after: str | None = None,
        limit: int = 50,
    ) -> dict:
        from services.memory_service import list_notes

        notes = await list_notes(folder=folder or None, limit=limit, workspace_path=workspace)

        if tag:
            notes = [n for n in notes if tag in n.get("tags", [])]
        if modified_after:
            notes = [n for n in notes if n.get("updated_at", "") >= modified_after]

        return {
            "results": [
                {
                    "path": n.get("path", ""),
                    "title": n.get("title", ""),
                    "folder": n.get("folder", ""),
                    "updated_at": n.get("updated_at", ""),
                }
                for n in notes[:limit]
            ]
        }

    @mcp.tool(
        name="jarvis_note_outline",
        description="Return only the headings + frontmatter of a note. Navigate a long note before reading.",
    )
    @audit("jarvis_note_outline", ws)
    @enforce_budget(max_tokens=1000)
    async def jarvis_note_outline(path: str) -> dict:
        from services.memory_service import get_note

        note = await get_note(path, workspace_path=workspace)
        content = note.get("content", "")

        headings: list[dict] = []
        for i, line in enumerate(content.splitlines(), 1):
            m = re.match(r"^(#{1,6})\s+(.+)$", line)
            if m:
                headings.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": i})

        result: dict = {"path": note.get("path", path), "headings": headings}
        if note.get("frontmatter"):
            result["frontmatter"] = note["frontmatter"]
        return result
