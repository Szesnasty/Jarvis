"""Jira tools — describe, list, blockers, dependencies, sprint risk, clustering."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_jira_describe_issue",
        description="Get a Jira issue by key with enriched summary, risk level, and graph neighbors.",
    )
    @audit("jarvis_jira_describe_issue", ws)
    @enforce_budget(max_tokens=4000)
    async def jarvis_jira_describe_issue(
        issue_key: str,
        include_comments: bool = False,
        include_neighbors: bool = True,
    ) -> dict:
        from services.tools.jira_tools import jira_describe_issue

        return await jira_describe_issue({"key": issue_key}, workspace_path=workspace)

    @mcp.tool(
        name="jarvis_jira_list_issues",
        description=(
            "Filter Jira issues by project, status, assignee, or sprint name. "
            "Returns key + title + status + assignee + risk. "
            "status values: 'to-do' (includes Ready For Dev, Draft, Backlog), "
            "'in-progress' (includes In Code Review, In Test, Ready For Test), "
            "'done' (includes Canceled). "
            "sprint accepts partial name, e.g. '43' matches 'Sprint 43'. "
            "Use jarvis_jira_sprint_risk for a full sprint risk overview instead."
        ),
    )
    @audit("jarvis_jira_list_issues", ws)
    @enforce_budget(max_tokens=2000)
    async def jarvis_jira_list_issues(
        project: str | None = None,
        status: Literal["to-do", "in-progress", "done"] | None = None,
        assignee: str | None = None,
        sprint: str | None = None,
        label: str | None = None,
        limit: int = 20,
    ) -> dict:
        from services.tools.jira_tools import jira_list_issues

        tool_input: dict = {"limit": limit}
        if project:
            tool_input["project_key"] = project
        if status:
            tool_input["status"] = status
        if assignee:
            tool_input["assignee"] = assignee
        if sprint:
            tool_input["sprint"] = sprint
        if label:
            tool_input["label"] = label

        results = await jira_list_issues(tool_input, workspace_path=workspace)
        return {"results": results}

    @mcp.tool(
        name="jarvis_jira_blockers_of",
        description="Find direct and transitive blockers of a Jira issue.",
    )
    @audit("jarvis_jira_blockers_of", ws)
    @enforce_budget(max_tokens=1500)
    async def jarvis_jira_blockers_of(issue_key: str) -> dict:
        from services.tools.jira_tools import jira_blockers_of

        return await asyncio.to_thread(
            jira_blockers_of, {"key": issue_key}, workspace_path=workspace
        )

    @mcp.tool(
        name="jarvis_jira_depends_on",
        description="Find issues that depend on a given Jira issue.",
    )
    @audit("jarvis_jira_depends_on", ws)
    @enforce_budget(max_tokens=1500)
    async def jarvis_jira_depends_on(issue_key: str) -> dict:
        from services.tools.jira_tools import jira_depends_on

        return await asyncio.to_thread(
            jira_depends_on, {"key": issue_key}, workspace_path=workspace
        )

    @mcp.tool(
        name="jarvis_jira_sprint_risk",
        description=(
            "Risk overview for a sprint: all issues with risk level, ambiguity, blocking chains, "
            "and assignee bottlenecks. "
            "If sprint name is omitted, uses the current/most active sprint automatically. "
            "Accepts partial sprint names (e.g. '43' matches 'Sprint 43'). "
            "Response already includes blocking_chain_length per issue *and* top_risks / top_unclear lists, "
            "so there is NO need to call jarvis_search_jira separately for blockers. "
            "Always prefer this tool over jarvis_jira_list_issues for sprint-level questions."
        ),
    )
    @audit("jarvis_jira_sprint_risk", ws)
    @enforce_budget(max_tokens=3000)
    async def jarvis_jira_sprint_risk(sprint: str | None = None, limit: int = 15) -> dict:
        from services.tools.jira_tools import jira_sprint_risk

        tool_input: dict = {"limit": limit}
        if sprint:
            tool_input["sprint_name"] = sprint
        return await jira_sprint_risk(tool_input, workspace_path=workspace)

    @mcp.tool(
        name="jarvis_jira_cluster_by_topic",
        description=(
            "Group Jira issues by business area / topic. "
            "Accepts optional project and sprint filters. "
            "Returns clusters with issue_count, avg_risk, and issue_keys."
        ),
    )
    @audit("jarvis_jira_cluster_by_topic", ws)
    @enforce_budget(max_tokens=3000)
    async def jarvis_jira_cluster_by_topic(
        project: str | None = None,
        sprint: str | None = None,
        max_clusters: int = 8,
    ) -> dict:
        from services.tools.jira_tools import jira_cluster_by_topic

        tool_input: dict = {"top_k": max_clusters}
        if project:
            tool_input["project_key"] = project
        if sprint:
            tool_input["sprint"] = sprint
        results = await jira_cluster_by_topic(tool_input, workspace_path=workspace)
        return {"results": results}
