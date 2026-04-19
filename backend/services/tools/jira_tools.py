"""Jira tool execution — deterministic queries over the local SQLite index."""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from services import graph_service


_PRIORITY_ORDER = {"highest": 0, "high": 1, "medium": 2, "low": 3, "lowest": 4}
_RISK_ORDER = {"high": 0, "medium": 1, "low": 2}


def _jira_db(workspace_path: Optional[Path] = None) -> sqlite3.Connection:
    from config import get_settings
    ws = workspace_path or get_settings().workspace_path
    db_path = ws / "app" / "jarvis.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


async def jira_list_issues(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> list[dict]:
    conn = _jira_db(workspace_path)
    try:
        clauses: list[str] = []
        params: list[Any] = []

        if tool_input.get("status"):
            clauses.append("i.status_category = ?")
            params.append(tool_input["status"])
        if tool_input.get("assignee"):
            clauses.append("i.assignee = ?")
            params.append(tool_input["assignee"])
        if tool_input.get("project_key"):
            clauses.append("i.project_key = ?")
            params.append(tool_input["project_key"])
        if tool_input.get("priority"):
            clauses.append("i.priority = ?")
            params.append(tool_input["priority"])

        join_sprint = ""
        if tool_input.get("sprint") or tool_input.get("sprint_state"):
            join_sprint = " JOIN issue_sprints s ON i.issue_key = s.issue_key"
            if tool_input.get("sprint"):
                clauses.append("LOWER(s.sprint_name) LIKE LOWER(?)")
                params.append(f"%{tool_input['sprint']}%")
            if tool_input.get("sprint_state"):
                clauses.append("s.sprint_state = ?")
                params.append(tool_input["sprint_state"])

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = max(1, min(50, tool_input.get("limit", 20)))

        sort_field = tool_input.get("sort", "updated")
        order = "i.updated_at DESC"
        if sort_field == "priority":
            order = "i.priority ASC, i.updated_at DESC"

        sql = (
            f"SELECT DISTINCT i.issue_key, i.title, i.status, i.status_category, "
            f"i.priority, i.assignee, i.issue_type "
            f"FROM issues i{join_sprint}{where} "
            f"ORDER BY {order} LIMIT ?"
        )
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            item: dict[str, Any] = {
                "key": row["issue_key"],
                "title": row["title"],
                "status": row["status"],
                "priority": row["priority"],
                "assignee": row["assignee"],
                "type": row["issue_type"],
            }
            # Sprint name (prefer ACTIVE, fall back to any sprint assigned)
            sprint_row = conn.execute(
                "SELECT sprint_name FROM issue_sprints "
                "WHERE issue_key = ? "
                "ORDER BY CASE WHEN sprint_state = 'ACTIVE' THEN 0 ELSE 1 END "
                "LIMIT 1",
                (row["issue_key"],),
            ).fetchone()
            item["sprint"] = sprint_row["sprint_name"] if sprint_row else None

            # Enrichment (risk + area only — no summary to save tokens)
            enr = conn.execute(
                "SELECT payload FROM latest_enrichment "
                "WHERE subject_type = 'jira_issue' AND subject_id = ?",
                (row["issue_key"],),
            ).fetchone()
            if enr:
                payload = json.loads(enr["payload"])
                item["risk"] = payload.get("risk_level")
                item["area"] = payload.get("business_area")
            results.append(item)

        # Post-sort by risk if requested
        if sort_field == "risk":
            results.sort(key=lambda x: _RISK_ORDER.get(
                (x.get("risk") or "low").lower(), 9
            ))

        return results
    finally:
        conn.close()


async def jira_describe_issue(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> dict:
    key = tool_input["key"].upper().strip()
    conn = _jira_db(workspace_path)
    try:
        row = conn.execute(
            "SELECT * FROM issues WHERE issue_key = ?", (key,)
        ).fetchone()
        if not row:
            return {"error": f"Issue {key} not found"}

        result: dict[str, Any] = {
            "key": row["issue_key"],
            "title": row["title"],
            "status": row["status"],
            "priority": row["priority"],
            "assignee": row["assignee"],
            "reporter": row["reporter"],
            "issue_type": row["issue_type"],
            "epic_key": row["epic_key"],
            "parent_key": row["parent_key"],
            "due_date": row["due_date"],
        }

        # Sprints
        sprints = conn.execute(
            "SELECT sprint_name, sprint_state FROM issue_sprints WHERE issue_key = ?",
            (key,),
        ).fetchall()
        result["sprints"] = [
            {"name": s["sprint_name"], "state": s["sprint_state"]} for s in sprints
        ]

        # Hard links
        hard_links: dict[str, list[str]] = defaultdict(list)
        for link_row in conn.execute(
            "SELECT target_key, link_type, direction FROM issue_links WHERE source_key = ?",
            (key,),
        ).fetchall():
            hard_links[link_row["link_type"]].append(link_row["target_key"])
        for link_row in conn.execute(
            "SELECT source_key, link_type, direction FROM issue_links WHERE target_key = ?",
            (key,),
        ).fetchall():
            reverse_type = link_row["link_type"]
            hard_links[reverse_type].append(link_row["source_key"])
        result["hard_links"] = dict(hard_links)

        # Enrichment
        enr = conn.execute(
            "SELECT payload FROM latest_enrichment "
            "WHERE subject_type = 'jira_issue' AND subject_id = ?",
            (key,),
        ).fetchone()
        if enr:
            result["enrichment"] = json.loads(enr["payload"])

        # Soft links from graph
        graph = graph_service.load_graph(workspace_path)
        soft_links: list[dict] = []
        if graph:
            node_id = f"issue:{key}"
            for edge in graph.edges:
                if edge.source == node_id and edge.origin in ("derived", "soft"):
                    soft_links.append({
                        "target": edge.target,
                        "type": edge.type,
                        "weight": edge.weight,
                    })
                elif edge.target == node_id and edge.origin in ("derived", "soft"):
                    soft_links.append({
                        "target": edge.source,
                        "type": edge.type,
                        "weight": edge.weight,
                    })
        result["soft_links"] = soft_links

        # Related notes/decisions from graph
        related: list[dict] = []
        if graph:
            node_id = f"issue:{key}"
            for edge in graph.edges:
                other = None
                if edge.source == node_id and edge.target.startswith("note:"):
                    other = edge.target
                elif edge.target == node_id and edge.source.startswith("note:"):
                    other = edge.source
                if other:
                    node = graph.nodes.get(other)
                    related.append({
                        "path": other.removeprefix("note:"),
                        "label": node.label if node else other,
                        "edge_type": edge.type,
                        "weight": edge.weight,
                    })
        result["related_notes"] = related

        return result
    finally:
        conn.close()


def _bfs_links(
    conn: sqlite3.Connection,
    start_key: str,
    link_type: str,
    direction: str,
    max_depth: int = 3,
) -> tuple[list[str], list[str]]:
    """BFS over issue_links. Returns (direct, transitive) key lists."""
    direct: list[str] = []
    transitive: list[str] = []
    visited: set[str] = {start_key}
    frontier: list[tuple[str, int]] = [(start_key, 0)]

    while frontier:
        current, depth = frontier.pop(0)
        if depth >= max_depth:
            continue
        if direction == "inbound":
            rows = conn.execute(
                "SELECT source_key FROM issue_links "
                "WHERE target_key = ? AND link_type = ?",
                (current, link_type),
            ).fetchall()
            neighbours = [r["source_key"] for r in rows]
        else:
            rows = conn.execute(
                "SELECT target_key FROM issue_links "
                "WHERE source_key = ? AND link_type = ?",
                (current, link_type),
            ).fetchall()
            neighbours = [r["target_key"] for r in rows]

        for nbr in neighbours:
            if nbr not in visited:
                visited.add(nbr)
                if depth == 0:
                    direct.append(nbr)
                else:
                    transitive.append(nbr)
                frontier.append((nbr, depth + 1))

    return direct, transitive


def jira_blockers_of(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> dict:
    key = tool_input["key"].upper().strip()
    conn = _jira_db(workspace_path)
    try:
        direct, transitive = _bfs_links(
            conn, key, "is blocked by", "outbound", max_depth=3,
        )
        d2, t2 = _bfs_links(conn, key, "blocks", "inbound", max_depth=3)
        all_direct = list(dict.fromkeys(direct + d2))
        all_transitive = list(dict.fromkeys(
            [k for k in transitive + t2 if k not in all_direct]
        ))

        # Likely blockers from graph soft edges
        likely: list[dict] = []
        graph = graph_service.load_graph(workspace_path)
        if graph:
            node_id = f"issue:{key}"
            for edge in graph.edges:
                if edge.type == "likely_dependency_on" and edge.target == node_id:
                    likely.append({"key": edge.source.removeprefix("issue:"), "confidence": edge.weight})
                elif edge.type == "likely_dependency_on" and edge.source == node_id:
                    likely.append({"key": edge.target.removeprefix("issue:"), "confidence": edge.weight})

        return {
            "key": key,
            "direct_blockers": all_direct,
            "transitive_blockers": all_transitive,
            "likely_blockers": likely,
        }
    finally:
        conn.close()


def jira_depends_on(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> dict:
    key = tool_input["key"].upper().strip()
    conn = _jira_db(workspace_path)
    try:
        direct, transitive = _bfs_links(
            conn, key, "blocks", "outbound", max_depth=3,
        )
        d2, t2 = _bfs_links(conn, key, "is blocked by", "inbound", max_depth=3)
        all_direct = list(dict.fromkeys(direct + d2))
        all_transitive = list(dict.fromkeys(
            [k for k in transitive + t2 if k not in all_direct]
        ))

        return {
            "key": key,
            "direct_dependents": all_direct,
            "transitive_dependents": all_transitive,
        }
    finally:
        conn.close()


async def jira_sprint_risk(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> dict:
    conn = _jira_db(workspace_path)
    try:
        sprint_name = tool_input.get("sprint_name")
        if not sprint_name:
            # Try ACTIVE state first
            row = conn.execute(
                "SELECT sprint_name FROM issue_sprints "
                "WHERE sprint_state = 'ACTIVE' LIMIT 1"
            ).fetchone()
            if not row:
                # Fallback: sprint with the most issues (most recent active)
                row = conn.execute(
                    "SELECT sprint_name, COUNT(*) as cnt FROM issue_sprints "
                    "GROUP BY sprint_name ORDER BY cnt DESC LIMIT 1"
                ).fetchone()
            if not row:
                return {"error": "No sprint found"}
            sprint_name = row["sprint_name"]
        else:
            # Resolve partial name (e.g. "43" → "Sprint 43")
            exact = conn.execute(
                "SELECT sprint_name FROM issue_sprints WHERE sprint_name = ? LIMIT 1",
                (sprint_name,),
            ).fetchone()
            if not exact:
                fuzzy = conn.execute(
                    "SELECT sprint_name FROM issue_sprints "
                    "WHERE LOWER(sprint_name) LIKE LOWER(?) "
                    "GROUP BY sprint_name ORDER BY COUNT(*) DESC LIMIT 1",
                    (f"%{sprint_name}%",),
                ).fetchone()
                if fuzzy:
                    sprint_name = fuzzy["sprint_name"]
                else:
                    return {"error": f"No sprint matching '{sprint_name}'"}

        rows = conn.execute(
            "SELECT i.issue_key, i.title, i.status, i.status_category, "
            "i.priority, i.assignee "
            "FROM issues i JOIN issue_sprints s ON i.issue_key = s.issue_key "
            "WHERE s.sprint_name = ? "
            "ORDER BY i.updated_at DESC",
            (sprint_name,),
        ).fetchall()

        issues: list[dict] = []
        top_risks: list[str] = []
        top_unclear: list[str] = []
        assignee_stats: dict[str, dict] = defaultdict(
            lambda: {"open_count": 0, "high_risk_count": 0}
        )

        for row in rows:
            item: dict[str, Any] = {
                "key": row["issue_key"],
                "title": row["title"],
                "status": row["status"],
                "priority": row["priority"],
                "assignee": row["assignee"],
            }

            enr = conn.execute(
                "SELECT payload FROM latest_enrichment "
                "WHERE subject_type = 'jira_issue' AND subject_id = ?",
                (row["issue_key"],),
            ).fetchone()
            risk = "low"
            ambiguity = "clear"
            if enr:
                payload = json.loads(enr["payload"])
                risk = payload.get("risk_level", "low")
                ambiguity = payload.get("ambiguity_level", "clear")
            item["risk"] = risk
            item["ambiguity"] = ambiguity

            _, transitive = _bfs_links(
                conn, row["issue_key"], "is blocked by", "outbound", max_depth=3,
            )
            item["blocking_chain_length"] = len(transitive) + (
                1 if transitive else 0
            )

            if risk == "high":
                top_risks.append(row["issue_key"])
            if ambiguity == "unclear":
                top_unclear.append(row["issue_key"])

            if row["status_category"] != "done" and row["assignee"]:
                stats = assignee_stats[row["assignee"]]
                stats["open_count"] += 1
                if risk == "high":
                    stats["high_risk_count"] += 1

            issues.append(item)

        bottlenecks = [
            {"assignee": name, **stats}
            for name, stats in sorted(
                assignee_stats.items(),
                key=lambda x: x[1]["open_count"],
                reverse=True,
            )
        ]

        # Pre-computed status summary so the agent doesn't have to count
        status_summary: dict[str, int] = defaultdict(int)
        for row in rows:
            cat = row["status_category"] or "unknown"
            status_summary[cat] += 1

        blocked_count = sum(
            1 for i in issues if i.get("blocking_chain_length", 0) > 0
        )

        return {
            "sprint_name": sprint_name,
            "total_issues": len(issues),
            "status_summary": dict(status_summary),
            "high_risk_count": len(top_risks),
            "blocked_count": blocked_count,
            "issues": issues,
            "top_risks": top_risks,
            "top_unclear": top_unclear,
            "bottlenecks": bottlenecks,
        }
    finally:
        conn.close()


async def jira_cluster_by_topic(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> list[dict]:
    conn = _jira_db(workspace_path)
    try:
        top_k = max(1, min(20, tool_input.get("top_k", 10)))
        root_keys = tool_input.get("root_keys")

        if root_keys:
            placeholders = ",".join("?" for _ in root_keys)
            keys_upper = [k.upper().strip() for k in root_keys]
            rows = conn.execute(
                f"SELECT issue_key FROM issues WHERE issue_key IN ({placeholders})",
                keys_upper,
            ).fetchall()
            issue_keys = [r["issue_key"] for r in rows]
        else:
            clauses: list[str] = []
            params: list[Any] = []
            join_sprint = ""
            if tool_input.get("project_key"):
                clauses.append("i.project_key = ?")
                params.append(tool_input["project_key"])
            if tool_input.get("sprint"):
                join_sprint = " JOIN issue_sprints s ON i.issue_key = s.issue_key"
                clauses.append("LOWER(s.sprint_name) LIKE LOWER(?)")
                params.append(f"%{tool_input['sprint']}%")
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = conn.execute(
                f"SELECT DISTINCT i.issue_key FROM issues i{join_sprint}{where} "
                f"ORDER BY i.updated_at DESC LIMIT 200",
                params,
            ).fetchall()
            issue_keys = [r["issue_key"] for r in rows]

        clusters: dict[str, list[dict]] = defaultdict(list)
        for key in issue_keys:
            enr = conn.execute(
                "SELECT payload FROM latest_enrichment "
                "WHERE subject_type = 'jira_issue' AND subject_id = ?",
                (key,),
            ).fetchone()
            area = "uncategorized"
            risk = "low"
            if enr:
                payload = json.loads(enr["payload"])
                area = payload.get("business_area", "uncategorized")
                risk = payload.get("risk_level", "low")
            clusters[area].append({"key": key, "risk": risk})

        result: list[dict] = []
        for area, items in sorted(
            clusters.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )[:top_k]:
            risks = [_RISK_ORDER.get(it["risk"], 2) for it in items]
            avg_risk_val = sum(risks) / len(risks) if risks else 2
            avg_risk = "high" if avg_risk_val < 1 else ("medium" if avg_risk_val < 2 else "low")
            result.append({
                "topic_label": area,
                "issue_count": len(items),
                "issue_keys": [it["key"] for it in items],
                "business_area": area,
                "avg_risk": avg_risk,
            })

        return result
    finally:
        conn.close()
