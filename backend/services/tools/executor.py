"""Tool execution dispatch — routes tool names to implementations."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from services import memory_service, planning_service, preference_service, graph_service, session_service
from services.tools.jira_tools import (
    jira_list_issues,
    jira_describe_issue,
    jira_blockers_of,
    jira_depends_on,
    jira_sprint_risk,
    jira_cluster_by_topic,
)


class ToolNotFoundError(Exception):
    pass


async def execute_tool(
    name: str,
    tool_input: dict[str, Any],
    workspace_path: Optional[Path] = None,
    session_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Execute a tool by name and return string result."""
    if name == "search_notes":
        results = await memory_service.list_notes(
            folder=tool_input.get("folder"),
            search=tool_input["query"],
            limit=tool_input.get("limit", 10),
            workspace_path=workspace_path,
        )
        if session_id:
            for r in results:
                session_service.record_note_access(session_id, r.get("path", ""))
        return json.dumps(results)

    if name == "read_note":
        note = await memory_service.get_note(
            tool_input["path"],
            workspace_path=workspace_path,
        )
        if session_id:
            session_service.record_note_access(session_id, tool_input["path"])
        return note["content"]

    if name == "write_note":
        await memory_service.create_note(
            tool_input["path"],
            tool_input["content"],
            workspace_path=workspace_path,
        )
        if session_id:
            session_service.record_note_access(session_id, tool_input["path"])
        # Incremental graph update (no full rebuild)
        try:
            graph_service.ingest_note(tool_input["path"], workspace_path)
        except Exception:
            pass
        return f"Note saved: {tool_input['path']}"

    if name == "append_note":
        await memory_service.append_note(
            tool_input["path"],
            tool_input["content"],
            workspace_path=workspace_path,
        )
        if session_id:
            session_service.record_note_access(session_id, tool_input["path"])
        # Incremental graph update (no full rebuild)
        try:
            graph_service.ingest_note(tool_input["path"], workspace_path)
        except Exception:
            pass
        return f"Content appended to: {tool_input['path']}"

    if name == "create_plan":
        result = await planning_service.create_plan(
            tool_input["title"],
            tool_input["items"],
            workspace_path=workspace_path,
        )
        return json.dumps(result)

    if name == "update_plan":
        content = await planning_service.update_plan_task(
            tool_input["path"],
            tool_input["task_index"],
            tool_input["checked"],
            workspace_path=workspace_path,
        )
        return content

    if name == "summarize_context":
        return await _execute_summarize(tool_input, workspace_path)

    if name == "save_preference":
        category = tool_input.get("category", "general")
        preference_service.save_preference(
            category,
            tool_input["rule"],
            workspace_path=workspace_path,
        )
        return f"Preference saved: [{category}] {tool_input['rule']}"

    if name == "query_graph":
        results = graph_service.query_entity(
            tool_input["entity"],
            relation_type=tool_input.get("relation_type"),
            depth=tool_input.get("depth", 1),
            workspace_path=workspace_path,
        )
        return json.dumps(results)

    if name == "ingest_url":
        from services.url_ingest import ingest_url
        result = await ingest_url(
            tool_input["url"],
            folder=tool_input.get("folder", "knowledge"),
            summarize=tool_input.get("summarize", False),
            api_key=api_key,
            workspace_path=workspace_path,
        )
        if session_id:
            session_service.record_note_access(session_id, result["path"])
        return json.dumps(result)

    if name == "web_search":
        from services.web_search import web_search
        results = await web_search(
            tool_input["query"],
            max_results=tool_input.get("max_results", 5),
        )
        return json.dumps(results)

    # ── Jira tools ────────────────────────────────────────────────────
    if name == "jira_list_issues":
        return json.dumps(await jira_list_issues(tool_input, workspace_path))

    if name == "jira_describe_issue":
        return json.dumps(await jira_describe_issue(tool_input, workspace_path))

    if name == "jira_blockers_of":
        return json.dumps(jira_blockers_of(tool_input, workspace_path))

    if name == "jira_depends_on":
        return json.dumps(jira_depends_on(tool_input, workspace_path))

    if name == "jira_sprint_risk":
        return json.dumps(await jira_sprint_risk(tool_input, workspace_path))

    if name == "jira_cluster_by_topic":
        return json.dumps(await jira_cluster_by_topic(tool_input, workspace_path))

    raise ToolNotFoundError(f"Unknown tool: {name}")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _execute_summarize(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> str:
    content = tool_input["content"]
    title = tool_input.get("title", "summary")
    save = tool_input.get("save", True)

    if not save:
        return content

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    note_path = f"summaries/{date}-{slug}.md"

    fm_content = (
        f"---\ntitle: {title}\ntype: summary\n"
        f"source: conversation\ntags: [summary]\n---\n\n"
        + content
    )

    try:
        await memory_service.create_note(note_path, fm_content, workspace_path)
    except memory_service.NoteExistsError:
        # Append instead if it already exists
        await memory_service.append_note(note_path, f"\n\n{content}", workspace_path)

    return json.dumps({"path": note_path, "saved": True})
