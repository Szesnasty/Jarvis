"""Meta tools — preferences, specialists, workspace stats."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_get_preferences",
        description="Return saved user preferences, optionally filtered by category prefix.",
    )
    @audit("jarvis_get_preferences", ws)
    @enforce_budget(max_tokens=1000)
    async def jarvis_get_preferences(category: str | None = None) -> dict:
        from services.preference_service import load_preferences

        prefs = await asyncio.to_thread(load_preferences, workspace_path=workspace)
        if category:
            prefs = {k: v for k, v in prefs.items() if k.startswith(category)}
        return {"preferences": prefs}

    @mcp.tool(
        name="jarvis_list_specialists",
        description="List user-defined specialist personas with their focus areas.",
    )
    @audit("jarvis_list_specialists", ws)
    @enforce_budget(max_tokens=1000)
    async def jarvis_list_specialists() -> dict:
        from services.specialist_service import list_specialists

        specs = await asyncio.to_thread(list_specialists, workspace_path=workspace)
        return {"results": specs}

    @mcp.tool(
        name="jarvis_workspace_stats",
        description="Counts and freshness: notes, Jira issues, chunks, graph nodes, last enrichment.",
    )
    @audit("jarvis_workspace_stats", ws)
    @enforce_budget(max_tokens=600)
    async def jarvis_workspace_stats() -> dict:
        db_path = workspace / "app" / "jarvis.db"
        stats: dict = {"workspace_path": str(workspace)}

        if not db_path.exists():
            stats["initialized"] = False
            return stats

        def _count(table: str) -> int:
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
                count = cur.fetchone()[0]
                conn.close()
                return count
            except Exception:
                return 0

        stats["note_count"] = await asyncio.to_thread(_count, "notes")
        stats["jira_issue_count"] = await asyncio.to_thread(_count, "issues")
        stats["chunk_count"] = await asyncio.to_thread(_count, "note_chunks")

        try:
            from services.graph_service import load_graph

            graph = await asyncio.to_thread(load_graph, workspace_path=workspace)
            stats["graph_node_count"] = len(graph.nodes) if graph else 0
            stats["graph_edge_count"] = len(graph.edges) if graph else 0
        except Exception:
            stats["graph_node_count"] = 0
            stats["graph_edge_count"] = 0

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.execute("SELECT MAX(created_at) FROM enrichments")
            row = cur.fetchone()
            stats["last_enrichment"] = row[0] if row and row[0] else None
            conn.close()
        except Exception:
            stats["last_enrichment"] = None

        stats["initialized"] = True
        return stats
