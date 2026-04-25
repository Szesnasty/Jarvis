"""Graph query API and incremental updates.

Public functions for querying, updating, and inspecting the graph.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set

from utils.markdown import parse_frontmatter

from services.graph_service.models import Edge, Graph, Node, extract_wiki_links
from services.graph_service.builder import (
    _memory_path,
    _save_and_cache,
    load_graph,
)


def get_neighbors(node_id: str, depth: int = 1, workspace_path: Optional[Path] = None) -> List[Dict]:
    graph = load_graph(workspace_path)
    if graph is None:
        return []
    return graph.get_neighbors(node_id, depth)


def query_entity(entity: str, relation_type: Optional[str] = None, depth: int = 1, workspace_path: Optional[Path] = None) -> List[Dict]:
    graph = load_graph(workspace_path)
    if graph is None:
        return []

    # Find matching node(s)
    entity_lower = entity.lower()
    matching_ids = []
    for node in graph.nodes.values():
        if entity_lower in node.label.lower() or entity_lower in node.id.lower():
            matching_ids.append(node.id)

    results = []
    seen = set()
    for nid in matching_ids:
        for neighbor in graph.get_neighbors(nid, depth):
            if neighbor["id"] not in seen:
                seen.add(neighbor["id"])
                results.append(neighbor)

    if relation_type:
        edge_targets = set()
        for e in graph.edges:
            if e.type == relation_type:
                edge_targets.add(e.source)
                edge_targets.add(e.target)
        results = [r for r in results if r["id"] in edge_targets]

    return results


def get_node_detail(node_id: str, workspace_path: Optional[Path] = None) -> Optional[Dict]:
    """Aggregate rich detail for a single node from graph + memory index."""
    graph = load_graph(workspace_path)
    if not graph or node_id not in graph.nodes:
        return None

    node = graph.nodes[node_id]
    neighbors = graph.get_neighbors(node_id, depth=1)

    connected_notes = [n for n in neighbors if n["type"] == "note"]
    connected_tags = [n["label"] for n in neighbors if n["type"] == "tag"]
    connected_people = [n["label"] for n in neighbors if n["type"] == "person"]

    # For note nodes: read preview from file
    preview = None
    metadata: Dict = {}
    note_path: Optional[str] = None
    if node.type == "note":
        path = node_id[5:]  # strip "note:"
        mem = _memory_path(workspace_path)
        filepath = mem / path
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                fm, body = parse_frontmatter(content)
                preview = body[:2000].strip()
                metadata = fm or {}
                note_path = path
            except Exception:
                pass
    elif node.type == "jira_issue":
        # Jira issues live at `memory/jira/{PROJECT}/{KEY}.md`. Look up the
        # exact path via the `issues` table (it was recorded at import time).
        issue_key = node_id[6:] if node_id.startswith("issue:") else node_id
        try:
            import sqlite3
            base = _memory_path(workspace_path).parent
            db_path = base / "app" / "jarvis.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                try:
                    row = conn.execute(
                        "SELECT note_path FROM issues WHERE issue_key = ?",
                        (issue_key,),
                    ).fetchone()
                finally:
                    conn.close()
                if row and row[0]:
                    note_path_raw = row[0]
                    # Back-compat: tolerate legacy "memory/" prefix.
                    if note_path_raw.startswith("memory/"):
                        note_path_raw = note_path_raw[len("memory/"):]
                    note_path = note_path_raw
                    filepath = _memory_path(workspace_path) / note_path_raw
                    if filepath.exists():
                        content = filepath.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        fm, body = parse_frontmatter(content)
                        preview = body[:2000].strip()
                        metadata = fm or {}
        except Exception:
            pass

    degree = sum(1 for e in graph.edges if e.source == node_id or e.target == node_id)

    return {
        "node": {"id": node.id, "type": node.type, "label": node.label, "folder": node.folder},
        "preview": preview,
        "metadata": metadata,
        "note_path": note_path,
        "connected_notes": connected_notes,
        "connected_tags": connected_tags,
        "connected_people": connected_people,
        "neighbor_count": len(neighbors),
        "degree": degree,
    }


def find_orphans(workspace_path: Optional[Path] = None) -> List[Dict]:
    """Find note nodes with degree 0 (no connections)."""
    graph = load_graph(workspace_path)
    if not graph:
        return []
    connected: Set[str] = set()
    for e in graph.edges:
        connected.add(e.source)
        connected.add(e.target)
    return [
        {"id": n.id, "label": n.label, "folder": n.folder}
        for n in graph.nodes.values()
        if n.type == "note" and n.id not in connected
    ]


# Step 25 PR 4 — semantic orphan repair.
#
# A "semantic orphan" is a note whose only graph connections are
# structural / low-signal edges (tagging into noisy buckets like `imported`,
# being part_of a folder, sitting next to other notes on the same day,
# being derived from a source). Such a note has not yet been linked to any
# other note in a meaningful way, so Smart Connect re-runs in aggressive
# mode to surface even weak suggestions.
DEFAULT_ORPHAN_IGNORE_EDGE_TYPES = frozenset({
    "tagged",
    "part_of",
    "temporal",
    "derived_from",
    "same_batch",         # provenance — not a semantic relation
    "suggested_related",  # unconfirmed — not yet user-validated
})

# Maximum weight contribution of a ``suggested_related`` edge in any
# graph-scoring context (retrieval, orphan checks).  Shared constant so
# Step 26b's retrieval guard and Step 26d's expansion weights stay in sync.
SUGGESTED_RELATED_MAX_WEIGHT: float = 0.35
DEFAULT_ORPHAN_IGNORE_TAGS = frozenset({
    "imported",
    "data",
    "xml",
    "csv",
})


def find_semantic_orphans(
    workspace_path: Optional[Path] = None,
    ignore_edge_types: Optional[Set[str]] = None,
    ignore_tags: Optional[Set[str]] = None,
) -> List[Dict]:
    """Find note nodes with no semantically meaningful neighbours.

    A note is a semantic orphan if **every** edge touching it is either:

      * of a type in ``ignore_edge_types`` (default: tagged, part_of,
        temporal, derived_from), **or**
      * a ``tagged`` edge whose tag node label is in ``ignore_tags``
        (default: imported, data, xml, csv).

    The original :func:`find_orphans` is kept for backwards compatibility
    (it returns degree-0 nodes only).
    """
    graph = load_graph(workspace_path)
    if not graph:
        return []

    ignore_types = set(ignore_edge_types or DEFAULT_ORPHAN_IGNORE_EDGE_TYPES)
    ignore_tag_labels = set(ignore_tags or DEFAULT_ORPHAN_IGNORE_TAGS)

    # Collect, per note id, the set of "meaningful" neighbour types it has.
    note_ids = {n.id for n in graph.nodes.values() if n.type == "note"}
    has_signal: Set[str] = set()

    for edge in graph.edges:
        for endpoint in (edge.source, edge.target):
            if endpoint not in note_ids:
                continue
            if edge.type in ignore_types:
                # Special case: a `tagged` edge into a non-noisy tag still
                # counts as signal. (Currently `tagged` is in the ignore
                # list — kept that way per spec — but if a future caller
                # removes it, the noisy-tag filter still applies.)
                continue
            if edge.type == "tagged":
                # Identify the tag endpoint and check its label.
                tag_id = edge.target if endpoint == edge.source else edge.source
                tag_node = graph.nodes.get(tag_id)
                tag_label = (tag_node.label if tag_node else tag_id.split(":", 1)[-1]).lower()
                if tag_label in ignore_tag_labels:
                    continue
            has_signal.add(endpoint)

    return [
        {"id": n.id, "label": n.label, "folder": n.folder}
        for n in graph.nodes.values()
        if n.type == "note" and n.id not in has_signal
    ]


def is_semantic_orphan(
    note_path: str,
    workspace_path: Optional[Path] = None,
    ignore_edge_types: Optional[Set[str]] = None,
    ignore_tags: Optional[Set[str]] = None,
) -> bool:
    """Convenience predicate — check whether a single note is a semantic orphan."""
    target = f"note:{note_path}"
    orphans = find_semantic_orphans(
        workspace_path=workspace_path,
        ignore_edge_types=ignore_edge_types,
        ignore_tags=ignore_tags,
    )
    return any(o["id"] == target for o in orphans)


def ingest_note(note_path: str, workspace_path: Optional[Path] = None) -> None:
    """Incrementally add/update a single note in the graph without full rebuild."""
    graph = load_graph(workspace_path)
    if graph is None:
        graph = Graph()

    mem = _memory_path(workspace_path)
    filepath = mem / note_path
    if not filepath.exists():
        return

    note_id = f"note:{note_path}"
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_frontmatter(content)
    except Exception:
        return

    # Remove old edges involving this note
    graph.edges = [e for e in graph.edges if e.source != note_id and e.target != note_id]

    # Re-add node
    folder = str(Path(note_path).parent) if "/" in note_path else ""
    graph.add_node(note_id, "note", fm.get("title", Path(note_path).stem), folder=folder)
    # Force update label in case it changed
    graph.nodes[note_id] = Node(
        id=note_id, type="note",
        label=fm.get("title", Path(note_path).stem), folder=folder,
    )

    # Re-add frontmatter edges
    for tag in fm.get("tags", []):
        tag_id = f"tag:{tag}"
        graph.add_node(tag_id, "tag", str(tag))
        graph.add_edge(note_id, tag_id, "tagged")

    for link in extract_wiki_links(body):
        graph.add_edge(note_id, f"note:{link}", "linked")

    for person in fm.get("people", []):
        person_id = f"person:{person}"
        graph.add_node(person_id, "person", str(person))
        graph.add_edge(note_id, person_id, "mentions")

    for related in fm.get("related", []):
        rel_path = related if related.endswith(".md") else related + ".md"
        graph.add_edge(note_id, f"note:{rel_path}", "related")

    if folder:
        area_id = f"area:{folder}"
        graph.add_node(area_id, "area", folder)
        graph.add_edge(note_id, area_id, "part_of")

    # Entity extraction on body (no API cost). Step 25 PR 2 — covers
    # person + organization + project + place via the shared helper, so
    # the incremental path stays in sync with the full rebuild pass.
    from services.graph_service.entity_edges import apply_extracted_entities

    existing_by_type = {
        "person": [n.label for n in graph.nodes.values() if n.type == "person"],
        "org": [n.label for n in graph.nodes.values() if n.type == "org"],
        "project": [n.label for n in graph.nodes.values() if n.type == "project"],
        "place": [n.label for n in graph.nodes.values() if n.type == "place"],
    }
    db_path = mem.parent / "app" / "jarvis.db"
    is_conversation = (
        fm.get("type") == "conversation"
        or note_path.startswith("conversations/")
    )
    apply_extracted_entities(
        graph,
        note_id=note_id,
        body=body,
        fm=fm,
        existing_labels_by_type=existing_by_type,
        db_path=db_path,
        is_conversation=is_conversation,
    )

    _save_and_cache(graph, workspace_path)


def add_conversation_to_graph(
    note_path: str,
    title: str,
    tags: List[str],
    topics: List[str],
    notes_accessed: List[str],
    workspace_path: Optional[Path] = None,
) -> None:
    """Incrementally add a conversation node + edges to the graph.

    Much cheaper than a full rebuild — only touches the new node.
    """
    graph = load_graph(workspace_path)
    if graph is None:
        graph = Graph()

    note_id = f"note:{note_path}"
    folder = str(Path(note_path).parent) if "/" in note_path else ""
    graph.add_node(note_id, "note", title, folder=folder)

    # Tags
    for tag in tags:
        tag_id = f"tag:{tag}"
        graph.add_node(tag_id, "tag", str(tag))
        graph.add_edge(note_id, tag_id, "tagged")

    # Topic tags
    for topic in topics:
        tag_id = f"tag:{topic}"
        graph.add_node(tag_id, "tag", str(topic))
        graph.add_edge(note_id, tag_id, "tagged")

    # Related notes (notes accessed during conversation)
    for related in notes_accessed:
        rel_path = related if related.endswith(".md") else related + ".md"
        target_id = f"note:{rel_path}"
        graph.add_edge(note_id, target_id, "related")

    # Folder membership
    if folder:
        area_id = f"area:{folder}"
        graph.add_node(area_id, "area", folder)
        graph.add_edge(note_id, area_id, "part_of")

    _save_and_cache(graph, workspace_path)
