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

    # Entity extraction on body (no API cost)
    from services.entity_extraction import extract_entities, clean_conversation_text
    existing_people = [n.label for n in graph.nodes.values() if n.type == "person"]
    fm_people = {str(p).lower() for p in fm.get("people", [])}

    # For conversation notes, clean markdown formatting before extraction
    # and use a lower confidence threshold (conversation content is trusted)
    is_conversation = fm.get("type") == "conversation" or note_path.startswith("conversations/")
    extraction_text = clean_conversation_text(body) if is_conversation else body
    min_confidence = 0.3 if is_conversation else 0.5

    for ent in extract_entities(extraction_text, existing_people):
        if ent.type == "person" and ent.confidence >= min_confidence:
            if ent.text.lower() not in fm_people:
                pid = f"person:{ent.text}"
                graph.add_node(pid, "person", ent.text)
                graph.add_edge(note_id, pid, "mentions")

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
