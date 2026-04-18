"""MCP tool definitions and handlers — 18 tools across 6 namespaces.

Each handler is a thin async wrapper around existing Jarvis services.
No business logic lives here — only argument mapping and result shaping.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Optional

from services.mcp.server import CostClass, ToolSpec

# ---------------------------------------------------------------------------
# Workspace path resolution
# ---------------------------------------------------------------------------

_workspace_path: Optional[Path] = None


def set_workspace_path(path: Path) -> None:
    global _workspace_path
    _workspace_path = path


def _wp() -> Path:
    if _workspace_path is None:
        from config import get_settings

        return get_settings().workspace_path
    return _workspace_path


# ---------------------------------------------------------------------------
# Search namespace (jarvis_search_*)
# ---------------------------------------------------------------------------


async def _handle_search_memory(args: dict[str, Any]) -> dict[str, Any]:
    from services.retrieval.pipeline import retrieve_with_intent

    query = args["query"]
    top_k = args.get("top_k", 5)
    scope = args.get("scope", "all")

    source_filter = None if scope == "all" else scope
    _intent, results = await retrieve_with_intent(
        query, limit=top_k, workspace_path=_wp()
    )
    if source_filter:
        results = [r for r in results if r.get("folder", "").startswith(source_filter) or source_filter in r.get("path", "")]

    return {
        "results": [
            {
                "path": r.get("path", ""),
                "title": r.get("title", ""),
                "snippet": r.get("_best_chunk", r.get("_best_section", ""))[:500],
                "score": round(r.get("_signals", {}).get("rerank", r.get("_signals", {}).get("cosine", 0.0)), 3),
                "source": "jira" if "jira" in r.get("path", "") else "notes",
            }
            for r in results[:top_k]
        ],
    }


async def _handle_search_notes(args: dict[str, Any]) -> dict[str, Any]:
    args = {**args, "scope": "notes"}
    return await _handle_search_memory(args)


async def _handle_search_jira(args: dict[str, Any]) -> dict[str, Any]:
    args = {**args, "scope": "jira"}
    return await _handle_search_memory(args)


# ---------------------------------------------------------------------------
# Note namespace (jarvis_note_*)
# ---------------------------------------------------------------------------


async def _handle_note_read(args: dict[str, Any]) -> dict[str, Any]:
    from services.memory_service import get_note

    path = args["path"]
    max_chars = args.get("max_chars", 8000)
    include_fm = args.get("include_frontmatter", True)

    note = await get_note(path, workspace_path=_wp())
    content = note.get("content", "")
    if len(content) > max_chars:
        content = content[:max_chars]

    result: dict[str, Any] = {
        "path": note.get("path", path),
        "title": note.get("title", ""),
        "content": content,
    }
    if include_fm and note.get("frontmatter"):
        result["frontmatter"] = note["frontmatter"]
    return result


async def _handle_note_list(args: dict[str, Any]) -> dict[str, Any]:
    from services.memory_service import list_notes

    folder = args.get("folder") or None
    limit = args.get("limit", 50)

    notes = await list_notes(folder=folder, limit=limit, workspace_path=_wp())

    # Apply optional filters
    tag_filter = args.get("tag")
    type_filter = args.get("type")
    modified_after = args.get("modified_after")

    if tag_filter:
        notes = [n for n in notes if tag_filter in n.get("tags", [])]
    if type_filter:
        fm = None  # list_notes doesn't return frontmatter type — skip for now
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


async def _handle_note_outline(args: dict[str, Any]) -> dict[str, Any]:
    from services.memory_service import get_note

    note = await get_note(args["path"], workspace_path=_wp())
    content = note.get("content", "")

    headings: list[dict[str, Any]] = []
    for i, line in enumerate(content.splitlines(), 1):
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            headings.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": i})

    result: dict[str, Any] = {"path": note.get("path", args["path"]), "headings": headings}
    if note.get("frontmatter"):
        result["frontmatter"] = note["frontmatter"]
    return result


# ---------------------------------------------------------------------------
# Graph namespace (jarvis_graph_*)
# ---------------------------------------------------------------------------


async def _handle_graph_query(args: dict[str, Any]) -> dict[str, Any]:
    from services.graph_service.queries import query_entity

    entity = args["entity"]
    relation_type = args.get("relation_type")
    depth = args.get("depth", 1)

    neighbors = await asyncio.to_thread(
        query_entity, entity, relation_type=relation_type, depth=depth, workspace_path=_wp()
    )
    return {"entity": entity, "results": neighbors}


async def _handle_graph_neighbors(args: dict[str, Any]) -> dict[str, Any]:
    from services.graph_service.queries import get_neighbors

    node_id = args["node_id"]
    depth = args.get("depth", 1)

    neighbors = await asyncio.to_thread(
        get_neighbors, node_id, depth=depth, workspace_path=_wp()
    )
    return {"node_id": node_id, "results": neighbors}


async def _handle_graph_entity_detail(args: dict[str, Any]) -> dict[str, Any]:
    from services.graph_service.queries import get_node_detail

    node_id = args["node_id"]
    detail = await asyncio.to_thread(get_node_detail, node_id, workspace_path=_wp())
    if detail is None:
        return {"error": f"Node '{node_id}' not found"}
    return detail


async def _handle_graph_path_between(args: dict[str, Any]) -> dict[str, Any]:
    from services.graph_service.queries import get_neighbors

    source = args["source"]
    target = args["target"]
    max_depth = args.get("max_depth", 4)

    # BFS shortest path using get_neighbors
    visited: set[str] = set()
    queue: list[tuple[str, list[str]]] = [(source, [source])]
    visited.add(source)

    for _ in range(max_depth):
        next_queue: list[tuple[str, list[str]]] = []
        for current, path in queue:
            neighbors = await asyncio.to_thread(
                get_neighbors, current, depth=1, workspace_path=_wp()
            )
            for n in neighbors:
                nid = n.get("id", "")
                if nid == target:
                    return {"source": source, "target": target, "path": path + [nid], "found": True}
                if nid not in visited:
                    visited.add(nid)
                    next_queue.append((nid, path + [nid]))
        queue = next_queue
        if not queue:
            break

    return {"source": source, "target": target, "path": [], "found": False}


# ---------------------------------------------------------------------------
# Jira namespace (jarvis_jira_*)
# ---------------------------------------------------------------------------


async def _handle_jira_describe_issue(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.jira_tools import jira_describe_issue

    tool_input = {"key": args["issue_key"]}
    result = await jira_describe_issue(tool_input, workspace_path=_wp())
    return result


async def _handle_jira_list_issues(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.jira_tools import jira_list_issues

    tool_input: dict[str, Any] = {}
    if "project" in args:
        tool_input["project_key"] = args["project"]
    if "status" in args:
        tool_input["status"] = args["status"]
    if "assignee" in args:
        tool_input["assignee"] = args["assignee"]
    if "sprint" in args:
        tool_input["sprint"] = args["sprint"]
    if "label" in args:
        tool_input["label"] = args.get("label")
    if "limit" in args:
        tool_input["limit"] = args["limit"]

    results = await jira_list_issues(tool_input, workspace_path=_wp())
    return {"results": results}


async def _handle_jira_blockers_of(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.jira_tools import jira_blockers_of

    tool_input = {"key": args["issue_key"]}
    return await asyncio.to_thread(jira_blockers_of, tool_input, workspace_path=_wp())


async def _handle_jira_depends_on(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.jira_tools import jira_depends_on

    tool_input = {"key": args["issue_key"]}
    return await asyncio.to_thread(jira_depends_on, tool_input, workspace_path=_wp())


async def _handle_jira_sprint_risk(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.jira_tools import jira_sprint_risk

    tool_input: dict[str, Any] = {}
    if "sprint" in args:
        tool_input["sprint_name"] = args["sprint"]
    if "limit" in args:
        tool_input["limit"] = args["limit"]

    return await jira_sprint_risk(tool_input, workspace_path=_wp())


async def _handle_jira_cluster_by_topic(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.jira_tools import jira_cluster_by_topic

    tool_input: dict[str, Any] = {}
    if "project" in args:
        tool_input["root_keys"] = []  # cluster_by_topic uses top_k instead
    if "min_cluster" in args:
        tool_input["top_k"] = args.get("max_clusters", 8)

    results = await jira_cluster_by_topic(tool_input, workspace_path=_wp())
    return {"results": results}


# ---------------------------------------------------------------------------
# Session namespace (jarvis_session_*)
# ---------------------------------------------------------------------------


async def _handle_session_recent(args: dict[str, Any]) -> dict[str, Any]:
    from services.session_service import list_sessions

    limit = args.get("limit", 10)
    days_back = args.get("days_back", 14)

    sessions = await list_sessions(workspace_path=_wp(), limit=limit)

    # Filter by days_back
    if days_back < 365:
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        sessions = [s for s in sessions if s.get("created_at", "") >= cutoff]

    return {"results": sessions[:limit]}


async def _handle_session_recent_decisions(args: dict[str, Any]) -> dict[str, Any]:
    """Mine decisions from recent sessions by scanning for decision markers."""
    from services.session_service import list_sessions, load_session

    days_back = args.get("days_back", 14)
    topic = args.get("topic")
    limit = args.get("limit", 10)

    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    sessions = await list_sessions(workspace_path=_wp(), limit=200)
    sessions = [s for s in sessions if s.get("created_at", "") >= cutoff]

    decision_markers = [
        "we decided", "let's go with", "final answer", "agreed to",
        "conclusion:", "decision:", "zdecydowaliśmy", "postanowiliśmy",
        "decyzja:", "ustaliliśmy",
    ]

    decisions: list[dict[str, Any]] = []
    for sess in sessions:
        try:
            full = await asyncio.to_thread(
                load_session, sess["session_id"], workspace_path=_wp()
            )
        except Exception:
            continue

        for msg in full.get("messages", []):
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            content_lower = content.lower()
            for marker in decision_markers:
                if marker in content_lower:
                    # Extract snippet around the marker
                    idx = content_lower.index(marker)
                    start = max(0, idx - 100)
                    end = min(len(content), idx + 300)
                    snippet = content[start:end].strip()

                    if topic and topic.lower() not in content_lower:
                        continue

                    decisions.append({
                        "session_id": sess["session_id"],
                        "ts": msg.get("timestamp", sess.get("created_at", "")),
                        "snippet": snippet,
                        "marker": marker,
                    })
                    break  # one decision per message

        if len(decisions) >= limit:
            break

    return {"results": decisions[:limit]}


async def _handle_session_tool_history(args: dict[str, Any]) -> dict[str, Any]:
    """Aggregate tool usage from recent sessions."""
    from services.session_service import list_sessions, load_session

    days_back = args.get("days_back", 7)

    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    sessions = await list_sessions(workspace_path=_wp(), limit=200)
    sessions = [s for s in sessions if s.get("created_at", "") >= cutoff]

    tool_counts: dict[str, int] = {}
    for sess in sessions:
        try:
            full = await asyncio.to_thread(
                load_session, sess["session_id"], workspace_path=_wp()
            )
        except Exception:
            continue
        for tool_name in full.get("tools_used", []):
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    sorted_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)
    return {"tools": [{"name": n, "count": c} for n, c in sorted_tools]}


# ---------------------------------------------------------------------------
# Meta namespace (jarvis_meta_*)
# ---------------------------------------------------------------------------


async def _handle_get_preferences(args: dict[str, Any]) -> dict[str, Any]:
    from services.preference_service import load_preferences

    prefs = await asyncio.to_thread(load_preferences, workspace_path=_wp())
    category = args.get("category")
    if category:
        prefs = {k: v for k, v in prefs.items() if k.startswith(category)}
    return {"preferences": prefs}


async def _handle_list_specialists(args: dict[str, Any]) -> dict[str, Any]:
    from services.specialist_service import list_specialists

    specs = await asyncio.to_thread(list_specialists, workspace_path=_wp())
    return {"results": specs}


async def _handle_workspace_stats(args: dict[str, Any]) -> dict[str, Any]:
    """Counts and freshness: notes, jira, chunks, graph nodes."""
    import sqlite3

    ws = _wp()
    db_path = ws / "app" / "jarvis.db"

    stats: dict[str, Any] = {"workspace_path": str(ws)}

    if not db_path.exists():
        stats["initialized"] = False
        return stats

    def _count_query(table: str) -> int:
        try:
            uri = f"file:{db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 — table names are hardcoded
            count = cur.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    stats["note_count"] = await asyncio.to_thread(_count_query, "notes")
    stats["jira_issue_count"] = await asyncio.to_thread(_count_query, "issues")
    stats["chunk_count"] = await asyncio.to_thread(_count_query, "note_chunks")

    # Graph node count
    try:
        from services.graph_service import load_graph

        graph = await asyncio.to_thread(load_graph, workspace_path=ws)
        stats["graph_node_count"] = len(graph.nodes) if graph else 0
        stats["graph_edge_count"] = len(graph.edges) if graph else 0
    except Exception:
        stats["graph_node_count"] = 0
        stats["graph_edge_count"] = 0

    # Last enrichment
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.execute("SELECT MAX(created_at) FROM enrichments")
        row = cur.fetchone()
        stats["last_enrichment"] = row[0] if row and row[0] else None
        conn.close()
    except Exception:
        stats["last_enrichment"] = None

    stats["initialized"] = True
    return stats


# ---------------------------------------------------------------------------
# Opt-in write tools
# ---------------------------------------------------------------------------


async def _handle_save_preference(args: dict[str, Any]) -> dict[str, Any]:
    from services.preference_service import save_preference

    category = args["category"]
    rule = args["rule"]
    key = f"{category}.{rule[:50]}"
    await asyncio.to_thread(save_preference, key, rule, workspace_path=_wp())
    return {"saved": True, "key": key}


async def _handle_append_note(args: dict[str, Any]) -> dict[str, Any]:
    from services.memory_service import append_note, NoteNotFoundError

    path = args["path"]
    text = args["text"]

    try:
        result = await append_note(path, text, workspace_path=_wp())
        return {"appended": True, "path": result.get("path", path)}
    except NoteNotFoundError:
        return {"error": f"Note '{path}' not found. Create it in Jarvis UI first."}


async def _handle_summarize_and_save(args: dict[str, Any]) -> dict[str, Any]:
    from services.tools.executor import execute_tool

    content = args["content"]
    title = args.get("title", "summary")
    save = args.get("save", True)

    tool_input = {"content": content, "title": title, "save": save}
    result_str = await execute_tool(
        "summarize_context", tool_input, workspace_path=_wp()
    )

    import json as _json

    try:
        return _json.loads(result_str)
    except (ValueError, TypeError):
        return {"content": result_str, "saved": False}


# ---------------------------------------------------------------------------
# Tool registry builder
# ---------------------------------------------------------------------------


def build_tools() -> list[ToolSpec]:
    """Construct the full 18-tool (+1 built-in continue) registry."""

    tools: list[ToolSpec] = []

    # -- Search namespace --------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_search_memory",
            description="Hybrid search (BM25 + semantic + reranker) over notes and Jira issues. Returns top-k chunks with paths and scores.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=4000,
            input_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 500},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    "scope": {"type": "string", "enum": ["all", "notes", "jira"], "default": "all"},
                },
                "additionalProperties": False,
            },
            handler=_handle_search_memory,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_search_notes",
            description="Search only knowledge-base notes (skips Jira). Same as search_memory with scope=notes.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=4000,
            input_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 500},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                },
                "additionalProperties": False,
            },
            handler=_handle_search_notes,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_search_jira",
            description="Search only Jira issues. Same as search_memory with scope=jira.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=4000,
            input_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 500},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                },
                "additionalProperties": False,
            },
            handler=_handle_search_jira,
        )
    )

    # -- Note namespace ----------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_note_read",
            description="Read a single note by workspace-relative path. Returns frontmatter + body.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=4000,
            input_schema={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "maxLength": 500},
                    "max_chars": {"type": "integer", "minimum": 200, "maximum": 50000, "default": 8000},
                    "include_frontmatter": {"type": "boolean", "default": True},
                },
                "additionalProperties": False,
            },
            handler=_handle_note_read,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_note_list",
            description="List notes in a folder. Returns paths + titles only — cheap directory listing.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=2000,
            input_schema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "default": "", "maxLength": 200},
                    "tag": {"type": "string", "maxLength": 50},
                    "type": {"type": "string", "maxLength": 50},
                    "modified_after": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                },
                "additionalProperties": False,
            },
            handler=_handle_note_list,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_note_outline",
            description="Return only the headings + frontmatter of a note. Navigate a long note before reading.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1000,
            input_schema={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "maxLength": 500},
                },
                "additionalProperties": False,
            },
            handler=_handle_note_outline,
        )
    )

    # -- Graph namespace ---------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_graph_query",
            description="Query the knowledge graph around a free-text entity. Returns neighbors with edge types.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=2000,
            input_schema={
                "type": "object",
                "required": ["entity"],
                "properties": {
                    "entity": {"type": "string", "maxLength": 200},
                    "relation_type": {"type": "string", "maxLength": 50},
                    "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
                },
                "additionalProperties": False,
            },
            handler=_handle_graph_query,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_graph_neighbors",
            description="Get neighbors of a canonical graph node ID (e.g. 'person:adam-nowak').",
            cost_class=CostClass.CHEAP,
            max_output_tokens=2000,
            input_schema={
                "type": "object",
                "required": ["node_id"],
                "properties": {
                    "node_id": {"type": "string", "maxLength": 200},
                    "depth": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
                },
                "additionalProperties": False,
            },
            handler=_handle_graph_neighbors,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_graph_entity_detail",
            description="Full details about a graph node: aliases, mentions, top related notes/issues.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1500,
            input_schema={
                "type": "object",
                "required": ["node_id"],
                "properties": {
                    "node_id": {"type": "string", "maxLength": 200},
                },
                "additionalProperties": False,
            },
            handler=_handle_graph_entity_detail,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_graph_path_between",
            description="Find shortest path between two entities in the knowledge graph.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=1500,
            input_schema={
                "type": "object",
                "required": ["source", "target"],
                "properties": {
                    "source": {"type": "string", "maxLength": 200},
                    "target": {"type": "string", "maxLength": 200},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 5, "default": 4},
                },
                "additionalProperties": False,
            },
            handler=_handle_graph_path_between,
        )
    )

    # -- Jira namespace ----------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_jira_describe_issue",
            description="Get a Jira issue by key with enriched summary, risk level, and graph neighbors.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=4000,
            input_schema={
                "type": "object",
                "required": ["issue_key"],
                "properties": {
                    "issue_key": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]+-[0-9]+$"},
                    "include_comments": {"type": "boolean", "default": False},
                    "include_neighbors": {"type": "boolean", "default": True},
                },
                "additionalProperties": False,
            },
            handler=_handle_jira_describe_issue,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_jira_list_issues",
            description="Filter Jira issues by project, status, assignee, sprint. Returns key + title + status.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=2000,
            input_schema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "maxLength": 50},
                    "status": {"type": "string", "enum": ["to-do", "in-progress", "done"]},
                    "assignee": {"type": "string", "maxLength": 100},
                    "sprint": {"type": "string", "maxLength": 100},
                    "label": {"type": "string", "maxLength": 50},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                },
                "additionalProperties": False,
            },
            handler=_handle_jira_list_issues,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_jira_blockers_of",
            description="Find direct and transitive blockers of a Jira issue.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1500,
            input_schema={
                "type": "object",
                "required": ["issue_key"],
                "properties": {
                    "issue_key": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]+-[0-9]+$"},
                },
                "additionalProperties": False,
            },
            handler=_handle_jira_blockers_of,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_jira_depends_on",
            description="Find issues that depend on a given Jira issue.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1500,
            input_schema={
                "type": "object",
                "required": ["issue_key"],
                "properties": {
                    "issue_key": {"type": "string", "pattern": r"^[A-Z][A-Z0-9_]+-[0-9]+$"},
                },
                "additionalProperties": False,
            },
            handler=_handle_jira_depends_on,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_jira_sprint_risk",
            description="Risk overview for a sprint: ranked at-risk issues with reasons.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=3000,
            input_schema={
                "type": "object",
                "properties": {
                    "sprint": {"type": "string", "maxLength": 100},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 15},
                },
                "additionalProperties": False,
            },
            handler=_handle_jira_sprint_risk,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_jira_cluster_by_topic",
            description="Group Jira issues by semantic topic using embeddings. Returns clusters.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=3000,
            input_schema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "maxLength": 50},
                    "sprint": {"type": "string", "maxLength": 100},
                    "max_clusters": {"type": "integer", "minimum": 2, "maximum": 20, "default": 8},
                },
                "additionalProperties": False,
            },
            handler=_handle_jira_cluster_by_topic,
        )
    )

    # -- Session namespace -------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_session_recent",
            description="List recent Jarvis chat sessions with topic + last message timestamp.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1500,
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    "days_back": {"type": "integer", "minimum": 1, "maximum": 365, "default": 14},
                },
                "additionalProperties": False,
            },
            handler=_handle_session_recent,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_session_recent_decisions",
            description="Find decisions from recent sessions (e.g. 'we decided', 'let's go with'). Filterable by topic.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=3000,
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "maxLength": 200},
                    "days_back": {"type": "integer", "minimum": 1, "maximum": 90, "default": 14},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10},
                },
                "additionalProperties": False,
            },
            handler=_handle_session_recent_decisions,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_session_tool_history",
            description="What tools were called in recent sessions and how often.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1000,
            input_schema={
                "type": "object",
                "properties": {
                    "days_back": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
                },
                "additionalProperties": False,
            },
            handler=_handle_session_tool_history,
        )
    )

    # -- Meta namespace ----------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_get_preferences",
            description="Return saved user preferences, optionally filtered by category.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1000,
            input_schema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "maxLength": 50},
                },
                "additionalProperties": False,
            },
            handler=_handle_get_preferences,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_list_specialists",
            description="List user-defined specialist personas with their focus areas.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=1000,
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=_handle_list_specialists,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_workspace_stats",
            description="Counts and freshness: notes, Jira issues, chunks, graph nodes, last enrichment.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=600,
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            handler=_handle_workspace_stats,
        )
    )

    # -- Opt-in writes -----------------------------------------------------
    tools.append(
        ToolSpec(
            name="jarvis_save_preference",
            description="Persist a user preference Jarvis will recall in every future session.",
            cost_class=CostClass.CHEAP,
            max_output_tokens=200,
            write=True,
            input_schema={
                "type": "object",
                "required": ["category", "rule"],
                "properties": {
                    "category": {"type": "string", "maxLength": 50},
                    "rule": {"type": "string", "maxLength": 1000},
                },
                "additionalProperties": False,
            },
            handler=_handle_save_preference,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_append_note",
            description="Append a block to an existing note (never creates new notes).",
            cost_class=CostClass.CHEAP,
            max_output_tokens=200,
            write=True,
            input_schema={
                "type": "object",
                "required": ["path", "text"],
                "properties": {
                    "path": {"type": "string", "maxLength": 500},
                    "text": {"type": "string", "maxLength": 10000},
                },
                "additionalProperties": False,
            },
            handler=_handle_append_note,
        )
    )

    tools.append(
        ToolSpec(
            name="jarvis_summarize_and_save",
            description="Summarize content and optionally save to a daily note.",
            cost_class=CostClass.MEDIUM,
            max_output_tokens=2000,
            write=True,
            input_schema={
                "type": "object",
                "required": ["content"],
                "properties": {
                    "content": {"type": "string", "maxLength": 50000},
                    "title": {"type": "string", "maxLength": 200, "default": "summary"},
                    "save": {"type": "boolean", "default": True},
                },
                "additionalProperties": False,
            },
            handler=_handle_summarize_and_save,
        )
    )

    return tools
