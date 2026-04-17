"""Graph data structures: Node, Edge, Graph + edge weight utilities.

Pure data layer — no I/O, no cache state, no external service calls.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


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
    evidence: tuple = ()  # ((source_chunk_idx, target_chunk_idx, similarity), ...)
    origin: str = "generic"  # provenance: "generic", "jira", "derived", etc.


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node_id: str, node_type: str, label: str, folder: str = "") -> None:
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(id=node_id, type=node_type, label=label, folder=folder)

    def add_edge(self, source: str, target: str, edge_type: str, weight: float = 1.0, origin: str = "generic") -> None:
        edge = Edge(source=source, target=target, type=edge_type, weight=weight, origin=origin)
        if edge not in self.edges:
            self.edges.append(edge)

    def remove_edges_by_origin(self, origin: str) -> int:
        """Remove all edges with the given origin. Returns count removed."""
        before = len(self.edges)
        self.edges = [e for e in self.edges if e.origin != origin]
        return before - len(self.edges)

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
        edges_list = []
        for e in self.edges:
            edge_dict = {
                "source": e.source, "target": e.target,
                "type": e.type, "weight": e.weight,
            }
            if e.origin != "generic":
                edge_dict["origin"] = e.origin
            if e.evidence:
                edge_dict["evidence"] = [
                    {"source_chunk": sc, "target_chunk": tc, "similarity": round(sim, 3)}
                    for sc, tc, sim in e.evidence
                ]
            edges_list.append(edge_dict)
        return {
            "nodes": [
                {"id": n.id, "type": n.type, "label": n.label, "folder": n.folder}
                for n in self.nodes.values()
            ],
            "edges": edges_list,
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


def compute_tag_idf(graph: Graph) -> Dict[str, float]:
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


def apply_edge_weights(graph: Graph) -> None:
    """Assign edge weights based on type and IDF for tags.

    Preserves evidence on similar_to edges. Does not overwrite
    weights on similar_to edges (those are set by similarity score).
    """
    idf = compute_tag_idf(graph)

    updated: List[Edge] = []
    for edge in graph.edges:
        if edge.type == "similar_to":
            # Keep existing weight and evidence from similarity computation
            updated.append(edge)
            continue
        base = _EDGE_BASE_WEIGHT.get(edge.type, 1.0)
        if edge.type == "tagged":
            tag_id = edge.target if edge.target.startswith("tag:") else edge.source
            weight = round(base * idf.get(tag_id, 0.5), 3)
        else:
            weight = base
        updated.append(Edge(source=edge.source, target=edge.target, type=edge.type, weight=weight, origin=edge.origin))

    graph.edges = updated
