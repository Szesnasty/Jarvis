"""Similarity edge computation for the knowledge graph.

Computes similar_to and temporal edges using chunk embeddings,
note embeddings, or keyword Jaccard as cascading fallbacks.
"""

import logging
from typing import Dict, List, Set

from services.graph_service.models import Edge, Graph

logger = logging.getLogger(__name__)

from pathlib import Path


def compute_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Add ``similar_to`` edges between semantically similar notes.

    Priority:
    1. Chunk-level embeddings (most precise, with evidence)
    2. Note-level embeddings (existing fallback)
    3. Keyword Jaccard (legacy fallback)
    """
    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]
    if not note_nodes:
        return []

    # Try chunk-level first (step 20c)
    try:
        chunk_edges = _compute_chunk_similarity_edges(graph, memory_path)
        if chunk_edges:
            return chunk_edges
    except Exception:
        pass

    try:
        embedding_edges = _compute_embedding_similarity_edges(graph, memory_path)
        if embedding_edges:
            return embedding_edges
    except Exception:
        pass

    return _compute_keyword_similarity_edges(graph, memory_path)


def _compute_chunk_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Build similar_to edges from chunk-pair cosine similarity with evidence."""
    import sqlite3
    from services.embedding_service import blob_to_vector, cosine_similarity

    ws = memory_path.parent
    db_path = ws / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT ce.path, ce.chunk_index, ce.embedding "
            "FROM chunk_embeddings ce"
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
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
    note_chunks: Dict[str, List[tuple]] = {}
    for path, idx, blob in rows:
        if path in graph_paths:
            vec = blob_to_vector(blob)
            note_chunks.setdefault(path, []).append((idx, vec))

    paths = list(note_chunks.keys())
    if len(paths) < 2:
        return []

    CHUNK_SIM_THRESHOLD = 0.55
    MAX_EDGES_PER_NODE = 5
    MAX_EVIDENCE_PER_EDGE = 3

    new_edges: List[Edge] = []
    edge_count: Dict[str, int] = {}

    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            path_a, path_b = paths[i], paths[j]
            node_a, node_b = f"note:{path_a}", f"note:{path_b}"

            if edge_count.get(node_a, 0) >= MAX_EDGES_PER_NODE:
                continue
            if edge_count.get(node_b, 0) >= MAX_EDGES_PER_NODE:
                continue

            chunk_pairs = []
            for idx_a, vec_a in note_chunks[path_a]:
                for idx_b, vec_b in note_chunks[path_b]:
                    sim = cosine_similarity(vec_a, vec_b)
                    if sim >= CHUNK_SIM_THRESHOLD:
                        chunk_pairs.append((idx_a, idx_b, sim))

            if not chunk_pairs:
                continue

            chunk_pairs.sort(key=lambda x: x[2], reverse=True)
            best_sim = chunk_pairs[0][2]
            evidence = tuple(chunk_pairs[:MAX_EVIDENCE_PER_EDGE])

            # Map [0.55, 1.0] -> [0.3, 1.0]
            weight = min(round(0.3 + (best_sim - 0.55) * (0.7 / 0.45), 3), 1.0)

            new_edges.append(Edge(
                source=node_a,
                target=node_b,
                type="similar_to",
                weight=weight,
                evidence=evidence,
            ))
            edge_count[node_a] = edge_count.get(node_a, 0) + 1
            edge_count[node_b] = edge_count.get(node_b, 0) + 1

    return new_edges


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
    from utils.markdown import parse_frontmatter

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


def compute_temporal_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Group notes by creation date and add temporal edges within same day."""
    from utils.markdown import parse_frontmatter

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


def prune_overloaded_tags(graph: Graph, max_degree: int = 30) -> None:
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
