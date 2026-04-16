"""Hybrid retrieval pipeline combining BM25, cosine similarity and graph scoring.

Each signal contributes a normalized [0,1] score. Weights are re-normalized
when a signal is unavailable so the pipeline degrades gracefully. Results
include a ``_signals`` dict for transparency/debugging.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set

from services import graph_service, memory_service

logger = logging.getLogger(__name__)

# Default fusion weights (rebalanced for chunk signal — step 20e)
WEIGHT_BM25 = 0.25
WEIGHT_COSINE = 0.40
WEIGHT_GRAPH = 0.35

# Semantic anchor matching thresholds (step 20b)
_ANCHOR_SIMILARITY_THRESHOLD = 0.50
_MAX_SEMANTIC_ANCHORS = 5


def _extract_query_entities_fallback(query: str, graph: graph_service.Graph) -> List[str]:
    """Legacy substring matching — used when semantic anchors unavailable."""
    query_lower = query.lower()
    matches = []
    for node in graph.nodes.values():
        if node.type in ("person", "tag", "area"):
            if node.label.lower() in query_lower:
                matches.append(node.id)
    return matches


async def _extract_query_anchors(
    query: str,
    graph: graph_service.Graph,
    workspace_path=None,
) -> List[str]:
    """Find graph nodes relevant to the query using semantic + substring matching.

    Strategy:
    1. Try semantic matching (node embeddings) — covers synonyms, partial names
    2. Fall back to substring matching if no node embeddings available
    3. Merge results from both, deduplicating
    """
    anchors: List[str] = []

    # Semantic matching (if node embeddings exist)
    embeddings_disabled = os.environ.get("JARVIS_DISABLE_EMBEDDINGS") == "1"
    if not embeddings_disabled:
        try:
            from services.embedding_service import find_similar_nodes, is_available
            if is_available():
                similar = await find_similar_nodes(
                    query, limit=_MAX_SEMANTIC_ANCHORS, workspace_path=workspace_path,
                )
                for node_id, label, score in similar:
                    if score >= _ANCHOR_SIMILARITY_THRESHOLD and node_id in graph.nodes:
                        anchors.append(node_id)
        except (ImportError, Exception):
            pass

    # Substring fallback (always runs — catches exact matches semantic might miss)
    query_lower = query.lower()
    for node in graph.nodes.values():
        if node.label.lower() in query_lower and node.id not in anchors:
            anchors.append(node.id)

    return anchors[:_MAX_SEMANTIC_ANCHORS]


def _shortest_weighted_path(
    graph: graph_service.Graph,
    start: str,
    end: str,
    max_depth: int = 3,
) -> Optional[float]:
    """BFS-based shortest weighted path distance between two nodes."""
    if start == end:
        return 0.0
    if start not in graph.nodes or end not in graph.nodes:
        return None

    visited = {start}
    frontier = {start}
    total_cost = 0.0

    for _ in range(max_depth):
        next_frontier = set()
        min_step_cost = float("inf")
        for edge in graph.edges:
            step_weight = 1.0 / (edge.weight + 0.01)
            if edge.source in frontier and edge.target not in visited:
                next_frontier.add(edge.target)
                min_step_cost = min(min_step_cost, step_weight)
                if edge.target == end:
                    return total_cost + step_weight
            if edge.target in frontier and edge.source not in visited:
                next_frontier.add(edge.source)
                min_step_cost = min(min_step_cost, step_weight)
                if edge.source == end:
                    return total_cost + step_weight
        if not next_frontier:
            break
        visited.update(next_frontier)
        frontier = next_frontier
        total_cost += min_step_cost if min_step_cost != float("inf") else 1.0

    return None


def _score_by_path(
    graph: graph_service.Graph,
    anchor_nodes: List[str],
    candidate_id: str,
    max_depth: int = 3,
) -> float:
    """Score a candidate by shortest weighted paths to anchor nodes."""
    total = 0.0
    for anchor in anchor_nodes:
        dist = _shortest_weighted_path(graph, candidate_id, anchor, max_depth)
        if dist is not None:
            total += 1.0 / (1.0 + dist)
    return total


def _compute_graph_score(
    node_id: str,
    graph: graph_service.Graph,
    anchors: List[str],
    candidate_ids: Set[str],
) -> float:
    """Combined graph score: edge connectivity + path distance + cluster bonus.

    Returns a value in the [0, 1] range.
    """
    if node_id not in graph.nodes:
        return 0.0

    # (a) Edge weight to other candidates in pool
    edge_score = 0.0
    neighbor_ids: Set[str] = set()
    cluster_count = 0
    for edge in graph.edges:
        other: Optional[str] = None
        if edge.source == node_id:
            other = edge.target
        elif edge.target == node_id:
            other = edge.source
        if other is None:
            continue
        if other in candidate_ids:
            edge_score += edge.weight
            neighbor_ids.add(other)
            if edge.type == "similar_to":
                cluster_count += 1

    # (b) Convergence bonus — connects to 3+ other candidates
    if len(neighbor_ids) >= 3:
        edge_score += 0.3

    # (c) Path distance to query entity anchors
    path_score = 0.0
    if anchors:
        path_score = _score_by_path(graph, anchors, node_id)

    # (d) Semantic cluster bonus
    cluster_bonus = min(cluster_count * 0.15, 0.45)

    raw = edge_score + path_score + cluster_bonus
    return min(raw, 1.0)


async def _get_note_meta(path: str, workspace_path=None) -> Optional[Dict]:
    """Look up note metadata directly from SQLite for candidates found
    only by embeddings (no BM25 match)."""
    import aiosqlite

    db_p = memory_service._db_path(workspace_path)
    if not db_p.exists():
        return None

    async with aiosqlite.connect(str(db_p)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT path, title, folder, tags, updated_at, word_count FROM notes WHERE path = ?",
            (path,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        try:
            tags = json.loads(row["tags"])
        except (json.JSONDecodeError, TypeError):
            tags = []
        return {
            "path": row["path"],
            "title": row["title"],
            "folder": row["folder"],
            "tags": tags,
            "updated_at": row["updated_at"],
            "word_count": row["word_count"],
        }


def _cluster_dedup(scored: List[Dict], limit: int) -> List[Dict]:
    """Keep at most 2 results per folder, trim to ``limit``."""
    seen_folders: Dict[str, int] = {}
    result: List[Dict] = []
    for item in scored:
        folder = item.get("folder", "") or ""
        if folder and seen_folders.get(folder, 0) >= 2:
            continue
        seen_folders[folder] = seen_folders.get(folder, 0) + 1
        result.append(item)
        if len(result) >= limit:
            break
    return result


async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> List[Dict]:
    """Hybrid retrieval combining BM25, chunk cosine similarity and graph scoring."""
    if not query or not query.strip():
        return []

    # --- Signal 1: BM25 candidates ---
    fts_candidates = await memory_service.list_notes(
        search=query,
        limit=limit * 3,
        workspace_path=workspace_path,
    )

    max_bm25 = max(
        (abs(c.get("_bm25_score", 0)) for c in fts_candidates), default=1.0
    ) or 1.0

    candidate_pool: Dict[str, Dict] = {}
    for c in fts_candidates:
        path = c["path"]
        bm25_norm = abs(c.get("_bm25_score", 0)) / max_bm25
        candidate_pool[path] = {
            **c,
            "_bm25": bm25_norm,
            "_cosine": 0.0,
            "_graph": 0.0,
            "_best_chunk": None,
            "_best_section": None,
        }

    # --- Signal 2: Chunk cosine (preferred) or note-level cosine fallback ---
    cosine_available = False
    embeddings_disabled = os.environ.get("JARVIS_DISABLE_EMBEDDINGS") == "1"
    if not embeddings_disabled:
        try:
            from services.embedding_service import is_available

            if is_available():
                # Try chunk-level search first
                chunk_results = None
                try:
                    from services.embedding_service import search_similar_chunks
                    chunk_results = await search_similar_chunks(
                        query, limit=limit * 3, workspace_path=workspace_path,
                    )
                except Exception:
                    pass

                if chunk_results:
                    cosine_available = True
                    for cr in chunk_results:
                        path = cr["path"]
                        score = max(0.0, min(1.0, cr["best_chunk_score"]))
                        if path in candidate_pool:
                            candidate_pool[path]["_cosine"] = score
                            candidate_pool[path]["_best_chunk"] = cr.get("best_chunk_text")
                            candidate_pool[path]["_best_section"] = cr.get("best_chunk_section")
                        else:
                            meta = await _get_note_meta(path, workspace_path)
                            if meta:
                                candidate_pool[path] = {
                                    **meta,
                                    "_bm25": 0.0,
                                    "_cosine": score,
                                    "_graph": 0.0,
                                    "_best_chunk": cr.get("best_chunk_text"),
                                    "_best_section": cr.get("best_chunk_section"),
                                }
                else:
                    # Fallback to note-level cosine
                    from services.embedding_service import search_similar
                    similar = await search_similar(
                        query, limit=limit * 3, workspace_path=workspace_path,
                    )
                    if similar:
                        cosine_available = True
                        for path, score in similar:
                            norm_score = max(0.0, min(1.0, float(score)))
                            if path in candidate_pool:
                                candidate_pool[path]["_cosine"] = norm_score
                            else:
                                meta = await _get_note_meta(path, workspace_path)
                                if meta:
                                    candidate_pool[path] = {
                                        **meta,
                                        "_bm25": 0.0,
                                        "_cosine": norm_score,
                                        "_graph": 0.0,
                                        "_best_chunk": None,
                                        "_best_section": None,
                                    }
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("Cosine retrieval failed: %s", exc)

    if not candidate_pool:
        return []

    # --- Signal 3: Graph scoring (with semantic anchors) ---
    graph = graph_service.load_graph(workspace_path)
    anchors: List[str] = []
    if graph:
        # Use semantic anchors if available, else substring fallback
        try:
            anchors = await _extract_query_anchors(query, graph, workspace_path)
        except Exception:
            anchors = _extract_query_entities_fallback(query, graph)

        candidate_ids = {f"note:{p}" for p in candidate_pool}
        for path, data in candidate_pool.items():
            node_id = f"note:{path}"
            data["_graph"] = _compute_graph_score(
                node_id, graph, anchors, candidate_ids
            )

    # --- Weighted fusion ---
    w_bm25 = WEIGHT_BM25
    w_cos = WEIGHT_COSINE if cosine_available else 0.0
    w_graph = WEIGHT_GRAPH if graph else 0.0
    total_w = w_bm25 + w_cos + w_graph or 1.0
    w_bm25 /= total_w
    w_cos /= total_w
    w_graph /= total_w

    scored: List[Dict] = []
    for data in candidate_pool.values():
        final = (
            w_bm25 * data["_bm25"]
            + w_cos * data["_cosine"]
            + w_graph * data["_graph"]
        )
        scored.append({
            **data,
            "_score": final,
            "_signals": {
                "bm25": round(data["_bm25"], 3),
                "cosine": round(data["_cosine"], 3),
                "graph": round(data["_graph"], 3),
            },
        })

    # Sort by fused score; tie-breaker: recency
    scored.sort(
        key=lambda x: (x["_score"], x.get("updated_at", "")),
        reverse=True,
    )

    result = _cluster_dedup(scored, limit)

    # Clean internal fields but KEEP _best_chunk and _best_section for context_builder
    for r in result:
        r.pop("_score", None)
        r.pop("_bm25", None)
        r.pop("_cosine", None)
        r.pop("_graph", None)
        r.pop("_bm25_score", None)
        r.pop("_node_id", None)

    return result
