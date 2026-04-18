"""Search tools — hybrid retrieval over notes + jira."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


async def _search(query: str, top_k: int, scope: str, workspace: Path) -> dict:
    from services.retrieval.pipeline import retrieve_with_intent

    _intent, results = await retrieve_with_intent(query, limit=top_k, workspace_path=workspace)

    if scope != "all":
        results = [
            r for r in results
            if r.get("folder", "").startswith(scope) or scope in r.get("path", "")
        ]

    return {
        "results": [
            {
                "path": r.get("path", ""),
                "title": r.get("title", ""),
                "snippet": r.get("_best_chunk", r.get("_best_section", ""))[:500],
                "score": round(
                    r.get("_signals", {}).get("rerank", r.get("_signals", {}).get("cosine", 0.0)),
                    3,
                ),
                "source": "jira" if "jira" in r.get("path", "") else "notes",
            }
            for r in results[:top_k]
        ],
    }


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_search_memory",
        description=(
            "Hybrid search (BM25 + semantic + reranker) over Jarvis notes and Jira issues. "
            "Returns top-k chunks with paths and scores."
        ),
    )
    @audit("jarvis_search_memory", ws)
    @enforce_budget(max_tokens=4000)
    async def jarvis_search_memory(
        query: str,
        top_k: int = 5,
        scope: Literal["all", "notes", "jira"] = "all",
    ) -> dict:
        return await _search(query, top_k, scope, workspace)

    @mcp.tool(
        name="jarvis_search_notes",
        description="Search only knowledge-base notes (skips Jira).",
    )
    @audit("jarvis_search_notes", ws)
    @enforce_budget(max_tokens=4000)
    async def jarvis_search_notes(query: str, top_k: int = 5) -> dict:
        return await _search(query, top_k, "notes", workspace)

    @mcp.tool(
        name="jarvis_search_jira",
        description="Search only Jira issues.",
    )
    @audit("jarvis_search_jira", ws)
    @enforce_budget(max_tokens=4000)
    async def jarvis_search_jira(query: str, top_k: int = 5) -> dict:
        return await _search(query, top_k, "jira", workspace)
