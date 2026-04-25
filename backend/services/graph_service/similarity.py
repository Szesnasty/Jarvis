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

    Exceptions during the chunk and note paths are logged (not silently
    swallowed) so quality regressions are observable. The keyword fallback
    runs only when both embedding paths produce zero edges.
    """
    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]
    if not note_nodes:
        return []

    try:
        chunk_edges = _compute_chunk_similarity_edges(graph, memory_path)
    except Exception:
        logger.exception("Chunk similarity edges failed; falling through")
        chunk_edges = []
    if chunk_edges:
        logger.info("Chunk similarity edges produced %d similar_to", len(chunk_edges))
        return chunk_edges

    try:
        embedding_edges = _compute_embedding_similarity_edges(graph, memory_path)
    except Exception:
        logger.exception("Note-level similarity edges failed; falling through")
        embedding_edges = []
    if embedding_edges:
        logger.info("Note-embedding similarity edges produced %d similar_to", len(embedding_edges))
        return embedding_edges

    keyword_edges = _compute_keyword_similarity_edges(graph, memory_path)
    if keyword_edges:
        logger.info("Keyword fallback produced %d similar_to edges", len(keyword_edges))
    else:
        logger.info("No similar_to edges produced (no embeddings, no keyword overlap)")
    return keyword_edges


def _compute_chunk_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Build similar_to edges from chunk-pair cosine similarity with evidence.

    Pipeline:
    1. ANN pre-filter — use note-level embeddings to drop pairs whose
       cosine < ``NOTE_PREFILTER_THRESHOLD``. Without this, cost is
       O(N²·M_a·M_b) chunk dot products; long ingested papers have
       thousands of chunks each so the brute-force loop is the reason
       this pass used to time out and produce zero edges.
    2. Vectorised chunk-pair cosine via numpy matmul on row-normalised
       matrices. Each surviving pair yields one (B_a × B_b) similarity
       matrix; a threshold mask keeps only the highest-quality cells.
    3. Per-note budget caps the fan-out at ``MAX_EDGES_PER_NODE``.
    """
    import sqlite3
    import numpy as np
    from services.embedding_service import blob_to_vector

    ws = memory_path.parent
    db_path = ws / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        try:
            chunk_rows = list(conn.execute(
                "SELECT path, chunk_index, embedding FROM chunk_embeddings"
            ))
        except sqlite3.OperationalError:
            return []

        try:
            note_emb_rows = list(conn.execute(
                "SELECT path, embedding FROM note_embeddings"
            ))
        except sqlite3.OperationalError:
            note_emb_rows = []
    finally:
        conn.close()

    if len(chunk_rows) < 2:
        return []

    graph_paths = {n.id[5:] for n in graph.nodes.values() if n.type == "note"}

    # --- Build per-note normalised chunk matrices ---
    # Cap chunks per note: papers ingested from PDFs can produce thousands
    # of chunks. After ~200 most-distinctive chunks per side, additional
    # comparisons add noise rather than signal.
    MAX_CHUNKS_PER_NOTE = 200
    note_chunks: Dict[str, List[tuple]] = {}
    for path, idx, blob in chunk_rows:
        if path in graph_paths:
            note_chunks.setdefault(path, []).append((idx, blob))

    chunk_matrices: Dict[str, tuple] = {}  # path -> (indices, normalised matrix)
    for path, items in note_chunks.items():
        if len(items) > MAX_CHUNKS_PER_NOTE:
            # Stride-sample so we cover the whole document, not just the head
            step = len(items) / MAX_CHUNKS_PER_NOTE
            items = [items[int(i * step)] for i in range(MAX_CHUNKS_PER_NOTE)]
        indices = [i for i, _ in items]
        vecs = np.array([blob_to_vector(b) for _, b in items], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        chunk_matrices[path] = (indices, vecs / norms)

    paths = list(chunk_matrices.keys())
    if len(paths) < 2:
        return []

    # --- ANN pre-filter via note-level embeddings ---
    # If a workspace has note-level embeddings, drop pairs with
    # note_cosine below the prefilter threshold. Cuts O(N²·M²) to
    # O(N²) note sims + chunked work only on the surviving pairs.
    NOTE_PREFILTER_THRESHOLD = 0.30
    note_vecs: Dict[str, "np.ndarray"] = {}
    for path, blob in note_emb_rows:
        if path in graph_paths:
            v = np.array(blob_to_vector(blob), dtype=np.float32)
            n = np.linalg.norm(v)
            note_vecs[path] = v / n if n > 0 else v

    CHUNK_SIM_THRESHOLD = 0.55
    MAX_EDGES_PER_NODE = 5
    MAX_EVIDENCE_PER_EDGE = 3

    new_edges: List[Edge] = []
    edge_count: Dict[str, int] = {}

    # Score every pair, then emit top-K per note (so the budget keeps
    # the BEST pairs instead of the first ones we scan).
    candidate_pairs: List[tuple] = []  # (best_sim, path_a, path_b, evidence_tuple)

    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            path_a, path_b = paths[i], paths[j]

            # ANN pre-filter
            va = note_vecs.get(path_a)
            vb = note_vecs.get(path_b)
            if va is not None and vb is not None:
                if float(va @ vb) < NOTE_PREFILTER_THRESHOLD:
                    continue

            indices_a, mat_a = chunk_matrices[path_a]
            indices_b, mat_b = chunk_matrices[path_b]

            sims = mat_a @ mat_b.T   # shape (M_a, M_b), normalised → cosine
            mask = sims >= CHUNK_SIM_THRESHOLD
            if not mask.any():
                continue

            # Top-K cells (by similarity) become evidence
            flat = sims.ravel()
            keep = max(1, min(MAX_EVIDENCE_PER_EDGE, int(mask.sum())))
            top_flat_idx = np.argpartition(-flat, keep - 1)[:keep]
            top_flat_idx = top_flat_idx[np.argsort(-flat[top_flat_idx])]

            evidence = tuple(
                (
                    int(indices_a[int(idx // sims.shape[1])]),
                    int(indices_b[int(idx % sims.shape[1])]),
                    float(flat[idx]),
                )
                for idx in top_flat_idx
            )
            best_sim = evidence[0][2]
            candidate_pairs.append((best_sim, path_a, path_b, evidence))

    # Per-note degree cap: keep the pairs that maximise the global best_sim
    candidate_pairs.sort(key=lambda x: -x[0])
    for best_sim, path_a, path_b, evidence in candidate_pairs:
        node_a, node_b = f"note:{path_a}", f"note:{path_b}"
        if edge_count.get(node_a, 0) >= MAX_EDGES_PER_NODE:
            continue
        if edge_count.get(node_b, 0) >= MAX_EDGES_PER_NODE:
            continue
        # Map [0.55, 1.0] → [0.3, 1.0]
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
            pruned.append(Edge(source=edge.source, target=edge.target, type=edge.type, weight=0.05, origin=edge.origin))
        else:
            pruned.append(edge)

    graph.edges = pruned
