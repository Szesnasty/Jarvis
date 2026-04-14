import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from config import get_settings
from utils.markdown import parse_frontmatter


@dataclass
class Node:
    id: str
    type: str
    label: str
    folder: str = ""


@dataclass(eq=True, frozen=True)
class Edge:
    source: str
    target: str
    type: str
    weight: float = 1.0


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node_id: str, node_type: str, label: str, folder: str = "") -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(id=node_id, type=node_type, label=label, folder=folder)

    def add_edge(self, source: str, target: str, edge_type: str, weight: float = 1.0) -> None:
        edge = Edge(source=source, target=target, type=edge_type, weight=weight)
        if edge not in self.edges:
            self.edges.append(edge)

    def get_neighbors(self, node_id: str, depth: int = 1) -> List[Dict]:
        if depth < 1 or node_id not in self.nodes:
            return []

        visited: Set[str] = {node_id}
        frontier: Set[str] = {node_id}
        result_edges: List[Edge] = []

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for edge in self.edges:
                if edge.source in frontier and edge.target not in visited:
                    next_frontier.add(edge.target)
                    result_edges.append(edge)
                if edge.target in frontier and edge.source not in visited:
                    next_frontier.add(edge.source)
                    result_edges.append(edge)
            visited.update(next_frontier)
            frontier = next_frontier

        neighbor_nodes = [
            self.nodes[nid] for nid in visited - {node_id} if nid in self.nodes
        ]
        return [
            {"id": n.id, "type": n.type, "label": n.label, "folder": n.folder}
            for n in neighbor_nodes
        ]

    def to_dict(self) -> Dict:
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "label": n.label, "folder": n.folder}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "type": e.type, "weight": e.weight}
                for e in self.edges
            ],
        }

    def stats(self) -> Dict:
        from collections import Counter

        degree: Counter = Counter()
        for e in self.edges:
            degree[e.source] += 1
            degree[e.target] += 1
        top = degree.most_common(5)
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "top_connected": [{"id": k, "degree": v} for k, v in top],
        }


_WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]")


def extract_wiki_links(body: str) -> List[str]:
    matches = _WIKI_LINK_RE.findall(body)
    results = []
    for m in matches:
        link = m.strip()
        if not link.endswith(".md"):
            link += ".md"
        results.append(link)
    return results


# Base edge weights by type
_EDGE_BASE_WEIGHT: Dict[str, float] = {
    "linked": 1.0,
    "related": 0.9,
    "mentions": 0.8,
    "tagged": 0.6,
    "part_of": 0.3,
    "similar_to": 0.5,
    "temporal": 0.2,
}


def compute_tag_idf(graph: "Graph") -> Dict[str, float]:
    """Compute IDF score for each tag node. Normalized to [0, 1]."""
    note_count = sum(1 for n in graph.nodes.values() if n.type == "note")
    if note_count == 0:
        return {}

    tag_freq: Dict[str, int] = {}
    for edge in graph.edges:
        if edge.type == "tagged":
            tag_id = edge.target if edge.target.startswith("tag:") else edge.source
            tag_freq[tag_id] = tag_freq.get(tag_id, 0) + 1

    max_idf = math.log(note_count + 1)
    idf: Dict[str, float] = {}
    for tag_id, freq in tag_freq.items():
        raw = math.log((note_count + 1) / (freq + 1))
        idf[tag_id] = round(raw / max_idf, 3) if max_idf > 0 else 0.5

    return idf


def _apply_edge_weights(graph: "Graph") -> None:
    """Assign edge weights based on type and IDF for tags."""
    idf = compute_tag_idf(graph)

    updated: List[Edge] = []
    for edge in graph.edges:
        base = _EDGE_BASE_WEIGHT.get(edge.type, 1.0)
        if edge.type == "tagged":
            tag_id = edge.target if edge.target.startswith("tag:") else edge.source
            weight = round(base * idf.get(tag_id, 0.5), 3)
        else:
            weight = base
        updated.append(Edge(source=edge.source, target=edge.target, type=edge.type, weight=weight))

    graph.edges = updated


_graph_cache: Optional[Graph] = None


def _memory_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _graph_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "graph" / "graph.json"


def _enrich_with_entities(graph: Graph, mem: Path) -> None:
    """Extract entities from note bodies and add person nodes/edges."""
    from services.entity_extraction import extract_entities

    existing_people = [n.label for n in graph.nodes.values() if n.type == "person"]

    for node in list(graph.nodes.values()):
        if node.type != "note":
            continue
        filepath = mem / node.id[5:]
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(content)
        except Exception:
            continue

        fm_people = {str(p).lower() for p in fm.get("people", [])}
        entities = extract_entities(body, existing_people)

        for ent in entities:
            if ent.type == "person" and ent.confidence >= 0.5:
                if ent.text.lower() not in fm_people:
                    person_id = f"person:{ent.text}"
                    graph.add_node(person_id, "person", ent.text)
                    graph.add_edge(node.id, person_id, "mentions")


def _resolve_bidirectional_links(graph: Graph) -> None:
    """For each linked edge A->B, add B->A if not already present."""
    forward_links = [(e.source, e.target) for e in graph.edges if e.type == "linked"]
    forward_set = set(forward_links)

    for src, tgt in forward_links:
        if (tgt, src) not in forward_set and tgt in graph.nodes:
            graph.add_edge(tgt, src, "linked", weight=0.6)
            forward_set.add((tgt, src))


def _compute_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Add ``similar_to`` edges between semantically similar notes.

    Primary strategy: stored embeddings (cosine similarity). If embeddings
    are unavailable or empty, fall back to keyword Jaccard similarity so
    the graph still gains some structural connections.
    """
    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]
    if not note_nodes:
        return []

    try:
        embedding_edges = _compute_embedding_similarity_edges(graph, memory_path)
        if embedding_edges:
            return embedding_edges
    except Exception:
        pass

    return _compute_keyword_similarity_edges(graph, memory_path)


def _compute_embedding_similarity_edges(
    graph: Graph, memory_path: Path
) -> List[Edge]:
    """Use stored embeddings to find semantically similar notes."""
    import sqlite3

    from services.embedding_service import blob_to_vector, cosine_similarity

    ws = memory_path.parent  # memory_path = <workspace>/memory
    db_path = ws / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT path, embedding FROM note_embeddings")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        # Table may not exist on a fresh workspace
        conn.close()
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if len(rows) < 2:
        return []

    graph_paths = {n.id[5:] for n in graph.nodes.values() if n.type == "note"}
    relevant: List[tuple] = [
        (path, blob_to_vector(blob))
        for path, blob in rows
        if path in graph_paths
    ]
    if len(relevant) < 2:
        return []

    new_edges: List[Edge] = []
    edge_count: Dict[str, int] = {}

    for i in range(len(relevant)):
        for j in range(i + 1, len(relevant)):
            path_a, vec_a = relevant[i]
            path_b, vec_b = relevant[j]
            sim = cosine_similarity(vec_a, vec_b)

            if sim < 0.65:
                continue

            node_a = f"note:{path_a}"
            node_b = f"note:{path_b}"

            if edge_count.get(node_a, 0) >= 5 or edge_count.get(node_b, 0) >= 5:
                continue

            # Map [0.65, 1.0] -> [0.3, 1.0]
            weight = min(round(0.3 + (sim - 0.65) * 2.0, 3), 1.0)
            new_edges.append(
                Edge(source=node_a, target=node_b, type="similar_to", weight=weight)
            )
            edge_count[node_a] = edge_count.get(node_a, 0) + 1
            edge_count[node_b] = edge_count.get(node_b, 0) + 1

    return new_edges


def _compute_keyword_similarity_edges(
    graph: Graph, memory_path: Path
) -> List[Edge]:
    """Legacy fallback: keyword Jaccard similarity."""
    from services.context_builder import _extract_keywords

    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]
    if len(note_nodes) > 500:
        return []

    note_keywords: Dict[str, Set[str]] = {}
    for node in note_nodes:
        path = node.id[5:]
        filepath = memory_path / path
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            _, body = parse_frontmatter(content)
        except Exception:
            continue
        text = f"{node.label} {body[:200]}"
        keywords = _extract_keywords(text)
        if len(keywords) >= 3:
            note_keywords[node.id] = keywords

    new_edges: List[Edge] = []
    edge_count: Dict[str, int] = {}
    node_ids = list(note_keywords.keys())
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            a, b = node_ids[i], node_ids[j]
            overlap = note_keywords[a] & note_keywords[b]
            union = note_keywords[a] | note_keywords[b]
            if not union:
                continue
            jaccard = len(overlap) / len(union)
            if jaccard >= 0.25 and len(overlap) >= 4:
                if edge_count.get(a, 0) >= 3 or edge_count.get(b, 0) >= 3:
                    continue
                weight = round(0.3 + jaccard * 0.4, 3)
                new_edges.append(Edge(source=a, target=b, type="similar_to", weight=weight))
                edge_count[a] = edge_count.get(a, 0) + 1
                edge_count[b] = edge_count.get(b, 0) + 1

    return new_edges


def _compute_temporal_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Group notes by creation date and add temporal edges within same day."""
    date_groups: Dict[str, List[str]] = {}

    for node in graph.nodes.values():
        if node.type != "note":
            continue
        path = node.id[5:]
        filepath = memory_path / path
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            fm, _ = parse_frontmatter(content)
        except Exception:
            continue
        created = fm.get("created_at", "") or fm.get("date", "")
        if isinstance(created, str) and len(created) >= 10:
            day = created[:10]
            date_groups.setdefault(day, []).append(node.id)

    edges: List[Edge] = []
    for day, node_ids in date_groups.items():
        if len(node_ids) < 2 or len(node_ids) > 10:
            continue
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                edges.append(Edge(source=node_ids[i], target=node_ids[j], type="temporal", weight=0.2))

    return edges


def _prune_overloaded_tags(graph: Graph, max_degree: int = 30) -> None:
    """Downweight tags that connect to more than max_degree notes."""
    tag_degree: Dict[str, int] = {}
    for edge in graph.edges:
        if edge.type == "tagged":
            tag_id = edge.target if edge.target.startswith("tag:") else edge.source
            tag_degree[tag_id] = tag_degree.get(tag_id, 0) + 1

    overloaded = {tid for tid, deg in tag_degree.items() if deg > max_degree}

    if not overloaded:
        return

    pruned: List[Edge] = []
    for edge in graph.edges:
        if edge.type == "tagged" and (edge.source in overloaded or edge.target in overloaded):
            pruned.append(Edge(source=edge.source, target=edge.target, type=edge.type, weight=0.05))
        else:
            pruned.append(edge)

    graph.edges = pruned


def rebuild_graph(workspace_path: Optional[Path] = None) -> Graph:
    global _graph_cache
    mem = _memory_path(workspace_path)
    graph = Graph()

    if not mem.exists():
        _save_and_cache(graph, workspace_path)
        return graph

    # Pass 1: Parse notes, extract frontmatter edges
    for md_file in sorted(mem.rglob("*.md")):
        rel = md_file.relative_to(mem).as_posix()
        content = md_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(content)

        note_id = f"note:{rel}"
        folder = str(md_file.relative_to(mem).parent) if "/" in rel else ""
        graph.add_node(note_id, "note", fm.get("title", md_file.stem), folder=folder)

        # Tags
        for tag in fm.get("tags", []):
            tag_id = f"tag:{tag}"
            graph.add_node(tag_id, "tag", str(tag))
            graph.add_edge(note_id, tag_id, "tagged")

        # Wiki links
        for link in extract_wiki_links(body):
            target_id = f"note:{link}"
            graph.add_edge(note_id, target_id, "linked")

        # People
        for person in fm.get("people", []):
            person_id = f"person:{person}"
            graph.add_node(person_id, "person", str(person))
            graph.add_edge(note_id, person_id, "mentions")

        # Related
        for related in fm.get("related", []):
            rel_path = related if related.endswith(".md") else related + ".md"
            graph.add_edge(note_id, f"note:{rel_path}", "related")

        # Folder membership
        if folder:
            area_id = f"area:{folder}"
            graph.add_node(area_id, "area", folder)
            graph.add_edge(note_id, area_id, "part_of")

    # Pass 2: Entity extraction (adds person nodes from body text)
    _enrich_with_entities(graph, mem)

    # Pass 3: Bidirectional wiki-link resolution
    _resolve_bidirectional_links(graph)

    # Pass 4: Keyword similarity edges (kill switch)
    settings = get_settings()
    if settings.similarity_edges_enabled:
        for edge in _compute_similarity_edges(graph, mem):
            graph.edges.append(edge)

    # Pass 5: Temporal edges (kill switch)
    if settings.temporal_edges_enabled:
        for edge in _compute_temporal_edges(graph, mem):
            graph.edges.append(edge)

    # Pass 6: Apply IDF-weighted edge weights
    _apply_edge_weights(graph)

    # Pass 7: Prune overloaded tags
    _prune_overloaded_tags(graph)

    _save_and_cache(graph, workspace_path)
    return graph


def _save_and_cache(graph: Graph, workspace_path: Optional[Path] = None) -> None:
    global _graph_cache
    _graph_cache = graph
    gp = _graph_path(workspace_path)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(graph.to_dict(), indent=2), encoding="utf-8")


def load_graph(workspace_path: Optional[Path] = None) -> Optional[Graph]:
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache

    gp = _graph_path(workspace_path)
    if not gp.exists():
        return None

    data = json.loads(gp.read_text(encoding="utf-8"))
    graph = Graph()
    for n in data.get("nodes", []):
        graph.add_node(n["id"], n["type"], n["label"], n.get("folder", ""))
    for e in data.get("edges", []):
        graph.add_edge(e["source"], e["target"], e["type"], e.get("weight", 1.0))

    _graph_cache = graph
    return graph


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
    if node.type == "note":
        path = node_id[5:]  # strip "note:"
        mem = _memory_path(workspace_path)
        filepath = mem / path
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                _fm, body = parse_frontmatter(content)
                preview = body[:2000].strip()
            except Exception:
                pass

    degree = sum(1 for e in graph.edges if e.source == node_id or e.target == node_id)

    return {
        "node": {"id": node.id, "type": node.type, "label": node.label, "folder": node.folder},
        "preview": preview,
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
    global _graph_cache
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
    from services.entity_extraction import extract_entities
    existing_people = [n.label for n in graph.nodes.values() if n.type == "person"]
    fm_people = {str(p).lower() for p in fm.get("people", [])}
    for ent in extract_entities(body, existing_people):
        if ent.type == "person" and ent.confidence >= 0.5:
            if ent.text.lower() not in fm_people:
                pid = f"person:{ent.text}"
                graph.add_node(pid, "person", ent.text)
                graph.add_edge(note_id, pid, "mentions")

    _save_and_cache(graph, workspace_path)


def invalidate_cache() -> None:
    global _graph_cache
    _graph_cache = None


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
