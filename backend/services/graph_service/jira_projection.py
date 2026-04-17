"""Jira → Graph projection: node types and hard edges.

Step 22b implementation. Reads the Jira SQLite tables populated by step 22a
and projects them as typed graph nodes and weighted edges.

Contract:
- Idempotent: removes all edges with origin="jira", then re-emits.
- Called after jira_ingest.run_import() and from rebuild_graph().
- Never touches Markdown files (read-only over SQLite).
- Person nodes reuse entity canonicalization when available.
"""

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from services.graph_service.models import Graph

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    """Lower-case slug for node IDs: 'Onboarding Sprint 14' → 'onboarding-sprint-14'."""
    return _SLUG_RE.sub("-", name.strip().lower()).strip("-")


@dataclass
class ProjectionStats:
    nodes_added: int = 0
    edges_added: int = 0
    edges_removed: int = 0
    issues: int = 0
    epics: int = 0
    sprints: int = 0
    projects: int = 0
    people: int = 0
    components: int = 0
    labels: int = 0


# ────────────────────────────────────────────────────────────
# Link-type mapping
# ────────────────────────────────────────────────────────────

# Maps link_type (the description text from issue_links) to a graph edge type.
# The description already captures the direction from source_key's perspective:
#   source_key=ONB-142, link_type="blocks", target=ONB-150
#     → ONB-142 blocks ONB-150
#   source_key=ONB-150, link_type="is blocked by", target=ONB-142
#     → ONB-150 is blocked by ONB-142 = ONB-150 depends_on ONB-142
_LINK_TYPE_MAP: Dict[str, tuple] = {
    # (edge_type, weight)
    "blocks": ("blocks", 1.0),
    "is blocked by": ("depends_on", 1.0),
    "duplicates": ("duplicate_of", 1.0),
    "is duplicated by": ("duplicate_of", 1.0),
    "relates to": ("relates_to", 0.9),
    "clones": ("duplicate_of", 1.0),
    "is cloned by": ("duplicate_of", 1.0),
}


def _resolve_person_id(display_name: str, db_path: Path, known_people: List[str]) -> str:
    """Resolve a Jira display name to a canonical person node ID.

    Uses entity_canonicalization if available, otherwise falls through
    to a simple slug.
    """
    if not display_name:
        return ""
    try:
        from services.entity_canonicalization import resolve_entity_sync
        canonical = resolve_entity_sync(display_name, "person", db_path, known_people)
        return canonical
    except (ImportError, Exception):
        return "person:%s" % display_name


# ────────────────────────────────────────────────────────────
# Main projection
# ────────────────────────────────────────────────────────────

def project_jira(workspace_path: Path, graph: Graph) -> ProjectionStats:
    """Idempotently project the Jira SQLite tables into the graph.

    Removes every edge where origin='jira' and rebuilds the set.
    Re-uses existing nodes and respects entity canonicalisation.
    """
    stats = ProjectionStats()
    db_path = workspace_path / "app" / "jarvis.db"
    if not db_path.exists():
        return stats

    # Phase 0: wipe previous jira edges (idempotent refresh)
    stats.edges_removed = graph.remove_edges_by_origin("jira")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        _project_issues(conn, graph, stats, db_path)
        _project_links(conn, graph, stats)
        _project_sprints(conn, graph, stats)
        _project_components(conn, graph, stats)
        _project_labels(conn, graph, stats)
        _project_comments(conn, graph, stats, db_path)
    finally:
        conn.close()

    return stats


def _add_jira_edge(graph: Graph, source: str, target: str, edge_type: str, weight: float = 1.0) -> None:
    """Add an edge with origin='jira'."""
    graph.add_edge(source, target, edge_type, weight=weight, origin="jira")


# ────────────────────────────────────────────────────────────
# Per-table projections
# ────────────────────────────────────────────────────────────

def _project_issues(conn: sqlite3.Connection, graph: Graph, stats: ProjectionStats, db_path: Path) -> None:
    """Create jira_issue, jira_epic, jira_project nodes + structural edges."""
    known_people = [n.label for n in graph.nodes.values() if n.type in ("person", "jira_person")]

    cursor = conn.execute(
        "SELECT issue_key, project_key, title, issue_type, status, "
        "status_category, assignee, reporter, epic_key, parent_key "
        "FROM issues"
    )
    seen_projects: Set[str] = set()

    for row in cursor:
        issue_key = row["issue_key"]
        project_key = row["project_key"]
        title = row["title"] or issue_key
        issue_type = (row["issue_type"] or "").strip()
        is_epic = issue_type.lower() == "epic"

        # 1. jira_issue node (always)
        issue_node_id = "issue:%s" % issue_key
        label = "%s — %s" % (issue_key, title) if title else issue_key
        graph.add_node(issue_node_id, "jira_issue", label)
        stats.issues += 1
        stats.nodes_added += 1

        # 2. jira_epic shadow node
        if is_epic:
            epic_node_id = "epic:%s" % issue_key
            graph.add_node(epic_node_id, "jira_epic", label)
            _add_jira_edge(graph, issue_node_id, epic_node_id, "is_epic_shadow", 1.0)
            stats.epics += 1
            stats.nodes_added += 1
            stats.edges_added += 1

        # 3. jira_project node
        if project_key and project_key not in seen_projects:
            project_node_id = "project:%s" % project_key
            graph.add_node(project_node_id, "jira_project", project_key)
            seen_projects.add(project_key)
            stats.projects += 1
            stats.nodes_added += 1

        if project_key:
            _add_jira_edge(graph, issue_node_id, "project:%s" % project_key, "in_project", 1.0)
            stats.edges_added += 1

        # 4. epic membership
        epic_key = row["epic_key"]
        if epic_key:
            epic_target = "epic:%s" % epic_key
            # Ensure epic node exists even if the epic issue wasn't imported
            if epic_target not in graph.nodes:
                graph.add_node(epic_target, "jira_epic", epic_key)
                stats.nodes_added += 1
            _add_jira_edge(graph, issue_node_id, epic_target, "in_epic", 1.0)
            stats.edges_added += 1

        # 5. parent
        parent_key = row["parent_key"]
        if parent_key:
            parent_target = "issue:%s" % parent_key
            if parent_target not in graph.nodes:
                graph.add_node(parent_target, "jira_issue", parent_key)
                stats.nodes_added += 1
            _add_jira_edge(graph, parent_target, issue_node_id, "parent_of", 1.0)
            stats.edges_added += 1

        # 6. assignee
        assignee = row["assignee"]
        if assignee:
            person_id = _resolve_person_id(assignee, db_path, known_people)
            if person_id:
                graph.add_node(person_id, "jira_person", assignee)
                _add_jira_edge(graph, issue_node_id, person_id, "assigned_to", 1.0)
                stats.edges_added += 1
                if person_id not in {n.id for n in graph.nodes.values() if n.type == "jira_person"}:
                    stats.people += 1
                    stats.nodes_added += 1

        # 7. reporter
        reporter = row["reporter"]
        if reporter:
            person_id = _resolve_person_id(reporter, db_path, known_people)
            if person_id:
                graph.add_node(person_id, "jira_person", reporter)
                _add_jira_edge(graph, issue_node_id, person_id, "reported_by", 0.9)
                stats.edges_added += 1


def _project_links(conn: sqlite3.Connection, graph: Graph, stats: ProjectionStats) -> None:
    """Project issue_links table into typed graph edges."""
    cursor = conn.execute(
        "SELECT source_key, target_key, link_type, direction FROM issue_links"
    )
    for row in cursor:
        source_key = row["source_key"]
        target_key = row["target_key"]
        link_type = (row["link_type"] or "").strip().lower()

        mapping = _LINK_TYPE_MAP.get(link_type)
        if not mapping:
            # Unknown link type → generic relates_to
            mapping = ("relates_to", 0.9)

        edge_type, weight = mapping

        source_node = "issue:%s" % source_key
        target_node = "issue:%s" % target_key

        # Ensure both nodes exist (might not be imported yet)
        if source_node not in graph.nodes:
            graph.add_node(source_node, "jira_issue", source_key)
            stats.nodes_added += 1
        if target_node not in graph.nodes:
            graph.add_node(target_node, "jira_issue", target_key)
            stats.nodes_added += 1

        _add_jira_edge(graph, source_node, target_node, edge_type, weight)
        stats.edges_added += 1


def _project_sprints(conn: sqlite3.Connection, graph: Graph, stats: ProjectionStats) -> None:
    """Create jira_sprint nodes and in_sprint edges."""
    seen_sprints: Set[str] = set()
    cursor = conn.execute(
        "SELECT issue_key, sprint_name, sprint_state FROM issue_sprints"
    )
    for row in cursor:
        sprint_name = row["sprint_name"]
        sprint_state = row["sprint_state"]
        sprint_slug = _slug(sprint_name)
        sprint_node_id = "sprint:%s" % sprint_slug

        if sprint_slug not in seen_sprints:
            # Store sprint state as part of the label for retrieval filtering
            graph.add_node(sprint_node_id, "jira_sprint", sprint_name)
            # Update with state metadata if we have it
            if sprint_state and sprint_node_id in graph.nodes:
                node = graph.nodes[sprint_node_id]
                # Store state in folder field (lightweight metadata slot)
                graph.nodes[sprint_node_id] = type(node)(
                    id=node.id, type=node.type, label=node.label,
                    folder=sprint_state,
                )
            seen_sprints.add(sprint_slug)
            stats.sprints += 1
            stats.nodes_added += 1

        issue_node_id = "issue:%s" % row["issue_key"]
        _add_jira_edge(graph, issue_node_id, sprint_node_id, "in_sprint", 1.0)
        stats.edges_added += 1


def _project_components(conn: sqlite3.Connection, graph: Graph, stats: ProjectionStats) -> None:
    """Create jira_component nodes and has_component edges."""
    seen: Set[str] = set()
    cursor = conn.execute("SELECT issue_key, component FROM issue_components")
    for row in cursor:
        component = row["component"]
        comp_slug = _slug(component)
        comp_node_id = "component:%s" % comp_slug

        if comp_slug not in seen:
            graph.add_node(comp_node_id, "jira_component", component)
            seen.add(comp_slug)
            stats.components += 1
            stats.nodes_added += 1

        issue_node_id = "issue:%s" % row["issue_key"]
        _add_jira_edge(graph, issue_node_id, comp_node_id, "has_component", 0.9)
        stats.edges_added += 1


def _project_labels(conn: sqlite3.Connection, graph: Graph, stats: ProjectionStats) -> None:
    """Create jira_label nodes and has_label edges."""
    seen: Set[str] = set()
    cursor = conn.execute("SELECT issue_key, label FROM issue_labels")
    for row in cursor:
        label = row["label"]
        label_slug = _slug(label)
        label_node_id = "label:%s" % label_slug

        if label_slug not in seen:
            graph.add_node(label_node_id, "jira_label", label)
            seen.add(label_slug)
            stats.labels += 1
            stats.nodes_added += 1

        issue_node_id = "issue:%s" % row["issue_key"]
        _add_jira_edge(graph, issue_node_id, label_node_id, "has_label", 0.8)
        stats.edges_added += 1


def _project_comments(conn: sqlite3.Connection, graph: Graph, stats: ProjectionStats, db_path: Path) -> None:
    """Add commented_by edges for unique comment authors per issue."""
    known_people = [n.label for n in graph.nodes.values() if n.type in ("person", "jira_person")]

    cursor = conn.execute(
        "SELECT DISTINCT issue_key, author FROM issue_comments WHERE author IS NOT NULL AND author != ''"
    )
    for row in cursor:
        author = row["author"]
        person_id = _resolve_person_id(author, db_path, known_people)
        if not person_id:
            continue

        graph.add_node(person_id, "jira_person", author)
        issue_node_id = "issue:%s" % row["issue_key"]
        _add_jira_edge(graph, issue_node_id, person_id, "commented_by", 0.7)
        stats.edges_added += 1
