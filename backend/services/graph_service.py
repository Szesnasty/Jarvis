import json
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


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node_id: str, node_type: str, label: str, folder: str = "") -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(id=node_id, type=node_type, label=label, folder=folder)

    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        edge = Edge(source=source, target=target, type=edge_type)
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
                {"source": e.source, "target": e.target, "type": e.type}
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


_graph_cache: Optional[Graph] = None


def _memory_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _graph_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "graph" / "graph.json"


def rebuild_graph(workspace_path: Optional[Path] = None) -> Graph:
    global _graph_cache
    mem = _memory_path(workspace_path)
    graph = Graph()

    if not mem.exists():
        _save_and_cache(graph, workspace_path)
        return graph

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
        graph.add_edge(e["source"], e["target"], e["type"])

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


def invalidate_cache() -> None:
    global _graph_cache
    _graph_cache = None
