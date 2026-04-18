"""Sessions tools — recent chat history, decisions, tool usage."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


_DECISION_MARKERS = [
    "we decided", "let's go with", "final answer", "agreed to",
    "conclusion:", "decision:", "zdecydowaliśmy", "postanowiliśmy",
    "decyzja:", "ustaliliśmy",
]


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_session_recent",
        description="List recent Jarvis chat sessions with topic + last message timestamp.",
    )
    @audit("jarvis_session_recent", ws)
    @enforce_budget(max_tokens=1500)
    async def jarvis_session_recent(limit: int = 10, days_back: int = 14) -> dict:
        from services.session_service import list_sessions

        sessions = await list_sessions(workspace_path=workspace, limit=limit)
        if days_back < 365:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
            sessions = [s for s in sessions if s.get("created_at", "") >= cutoff]
        return {"results": sessions[:limit]}

    @mcp.tool(
        name="jarvis_session_recent_decisions",
        description=(
            "Find decisions from recent sessions (e.g. 'we decided', 'let's go with'). "
            "Filterable by topic substring."
        ),
    )
    @audit("jarvis_session_recent_decisions", ws)
    @enforce_budget(max_tokens=3000)
    async def jarvis_session_recent_decisions(
        topic: str | None = None,
        days_back: int = 14,
        limit: int = 10,
    ) -> dict:
        from services.session_service import list_sessions, load_session

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        sessions = await list_sessions(workspace_path=workspace, limit=200)
        sessions = [s for s in sessions if s.get("created_at", "") >= cutoff]

        decisions: list[dict] = []
        for sess in sessions:
            try:
                full = await asyncio.to_thread(
                    load_session, sess["session_id"], workspace_path=workspace
                )
            except Exception:
                continue

            for msg in full.get("messages", []):
                content = msg.get("content", "")
                if not isinstance(content, str):
                    continue
                content_lower = content.lower()
                for marker in _DECISION_MARKERS:
                    if marker in content_lower:
                        if topic and topic.lower() not in content_lower:
                            continue
                        idx = content_lower.index(marker)
                        snippet = content[max(0, idx - 100): min(len(content), idx + 300)].strip()
                        decisions.append({
                            "session_id": sess["session_id"],
                            "ts": msg.get("timestamp", sess.get("created_at", "")),
                            "snippet": snippet,
                            "marker": marker,
                        })
                        break

            if len(decisions) >= limit:
                break

        return {"results": decisions[:limit]}

    @mcp.tool(
        name="jarvis_session_tool_history",
        description="Aggregated tool usage from recent sessions (which tools, how often).",
    )
    @audit("jarvis_session_tool_history", ws)
    @enforce_budget(max_tokens=1000)
    async def jarvis_session_tool_history(days_back: int = 7) -> dict:
        from services.session_service import list_sessions, load_session

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        sessions = await list_sessions(workspace_path=workspace, limit=200)
        sessions = [s for s in sessions if s.get("created_at", "") >= cutoff]

        tool_counts: dict[str, int] = {}
        for sess in sessions:
            try:
                full = await asyncio.to_thread(
                    load_session, sess["session_id"], workspace_path=workspace
                )
            except Exception:
                continue
            for tool_name in full.get("tools_used", []):
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
        return {"tools": [{"name": n, "count": c} for n, c in sorted_tools]}
