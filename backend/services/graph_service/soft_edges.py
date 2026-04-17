"""Derived (soft) graph edges with confidence scoring.

Step 22d: produces confidence-weighted edges that connect semantically
related items based on embeddings, enrichment payloads and text signals.

All derived edges carry ``origin="derived"`` and are fully rebuildable
from inputs alone.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.graph_service.models import Edge, Graph

logger = logging.getLogger(__name__)

# ── Edge catalogue ───────────────────────────────────────────

EDGE_SAME_TOPIC = "same_topic_as"
EDGE_SAME_AREA = "same_business_area_as"
EDGE_SAME_RISK = "same_risk_cluster_as"
EDGE_LIKELY_DEP = "likely_dependency_on"
EDGE_SAME_PROBLEM = "implementation_of_same_problem"

CONFIDENCE_FLOORS: Dict[str, float] = {
    EDGE_SAME_TOPIC: 0.60,
    EDGE_SAME_AREA: 0.55,
    EDGE_SAME_RISK: 0.60,
    EDGE_LIKELY_DEP: 0.65,
    EDGE_SAME_PROBLEM: 0.70,
}

MAX_OUT_DEGREE: Dict[str, int] = {
    EDGE_SAME_TOPIC: 8,
    EDGE_SAME_AREA: 10,
    EDGE_SAME_RISK: 8,
    EDGE_LIKELY_DEP: 5,
    EDGE_SAME_PROBLEM: 6,
}

# Global safety valve: derived edges ≤ 5 * |nodes|
DENSITY_MULTIPLIER = 5
FLOOR_RAISE_STEP = 0.05


# ── Signal helpers (pure functions) ──────────────────────────

def node_cosine(vec_a: List[float], vec_b: List[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on degenerate input."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


def keyword_jaccard(kw_a: List[str], kw_b: List[str]) -> float:
    """Jaccard similarity of two keyword lists."""
    set_a = {k.lower().strip() for k in kw_a if k.strip()}
    set_b = {k.lower().strip() for k in kw_b if k.strip()}
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def top_k_mean(values: List[float], k: int = 3) -> float:
    """Mean of the top-k values. Returns 0.0 if empty."""
    if not values:
        return 0.0
    sorted_vals = sorted(values, reverse=True)[:k]
    return sum(sorted_vals) / len(sorted_vals)


# ── Confidence formulas ──────────────────────────────────────

def confidence_same_topic(
    node_sim: float,
    chunk_sims: List[float],
    kw_jaccard: float,
) -> float:
    """
    confidence(same_topic_as, a, b) =
        0.55 * cos(node_a, node_b)
      + 0.35 * top_k_mean(chunk_cosine, k=3)
      + 0.10 * keyword_jaccard(a, b)
    """
    return (
        0.55 * node_sim
        + 0.35 * top_k_mean(chunk_sims, k=3)
        + 0.10 * kw_jaccard
    )


def confidence_same_business_area(
    areas_match: bool,
    topic_signal: float,
) -> float:
    """Returns 0.0 if areas don't match, otherwise blends area match with topic."""
    if not areas_match:
        return 0.0
    return 0.50 + 0.50 * topic_signal


def confidence_same_risk_cluster(
    same_area_and_risk: bool,
    topic_signal: float,
) -> float:
    """Returns 0.0 if area+risk don't match, otherwise blends with topic."""
    if not same_area_and_risk:
        return 0.0
    return 0.50 + 0.50 * topic_signal


def confidence_likely_dependency(
    has_forward_ref: bool,
    topic_signal: float,
    has_hard_blocks: bool,
) -> float:
    """Directed dependency confidence. Suppressed if a hard `blocks` edge exists."""
    if has_hard_blocks or not has_forward_ref:
        return 0.0
    return 0.40 + 0.60 * topic_signal


def confidence_same_problem(
    high_chunk_count: int,
    same_area: bool,
    best_chunk_sim: float,
) -> float:
    """Requires ≥3 highly-similar chunk pairs AND same business area."""
    if high_chunk_count < 3 or not same_area:
        return 0.0
    count_factor = min(high_chunk_count / 6.0, 1.0)
    return 0.40 + 0.35 * best_chunk_sim + 0.25 * count_factor


# ── Data loading ─────────────────────────────────────────────

def _load_node_embeddings(conn: sqlite3.Connection) -> Dict[str, List[float]]:
    """Load node_embeddings as {node_id: vector}."""
    from services.embedding_service import blob_to_vector
    result: Dict[str, List[float]] = {}
    try:
        for row in conn.execute("SELECT node_id, embedding FROM node_embeddings"):
            result[row[0]] = blob_to_vector(row[1])
    except sqlite3.OperationalError:
        pass
    return result


def _load_chunk_embeddings(conn: sqlite3.Connection) -> Dict[str, List[Tuple[int, List[float]]]]:
    """Load chunk_embeddings grouped by path: {path: [(chunk_idx, vec), ...]}."""
    from services.embedding_service import blob_to_vector
    result: Dict[str, List[Tuple[int, List[float]]]] = {}
    try:
        for row in conn.execute("SELECT path, chunk_index, embedding FROM chunk_embeddings"):
            result.setdefault(row[0], []).append((row[1], blob_to_vector(row[2])))
    except sqlite3.OperationalError:
        pass
    return result


def _load_enrichments(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Load latest enrichment payloads: {(subject_type:subject_id): payload}."""
    result: Dict[str, Dict[str, Any]] = {}
    try:
        for row in conn.execute(
            "SELECT subject_type, subject_id, payload FROM latest_enrichment"
        ):
            key = f"{row[0]}:{row[1]}"
            try:
                result[key] = json.loads(row[2] or "{}")
            except json.JSONDecodeError:
                pass
    except sqlite3.OperationalError:
        pass
    return result


def _build_hard_edge_index(graph: Graph) -> Set[Tuple[str, str, str]]:
    """Set of (source, target, type) for hard edges that suppress soft ones."""
    suppress_types = {"blocks", "depends_on", "duplicate_of"}
    index: Set[Tuple[str, str, str]] = set()
    for e in graph.edges:
        if e.origin != "derived" and e.type in suppress_types:
            index.add((e.source, e.target, e.type))
            index.add((e.target, e.source, e.type))
    return index


def _node_id_to_enrichment_key(node_id: str) -> Optional[str]:
    """Map graph node_id to enrichment lookup key."""
    if node_id.startswith("issue:"):
        return f"jira_issue:{node_id[6:]}"
    if node_id.startswith("note:"):
        return f"note:{node_id[5:]}"
    return None


def _node_id_to_path(node_id: str) -> Optional[str]:
    """Extract content path from a node ID for chunk embedding lookup."""
    if node_id.startswith("note:"):
        return node_id[5:]
    return None


def _find_forward_references(
    node_id: str, target_id: str, graph: Graph, conn: sqlite3.Connection
) -> bool:
    """Check if node_id's content textually references target_id's key."""
    if not node_id.startswith("issue:") or not target_id.startswith("issue:"):
        return False
    target_key = target_id[6:]  # e.g. "ONB-123"
    source_key = node_id[6:]
    try:
        row = conn.execute(
            "SELECT description FROM issues WHERE issue_key = ?", (source_key,)
        ).fetchone()
        if row and row[0] and target_key in row[0]:
            return True
        # Check comments too
        for crow in conn.execute(
            "SELECT body FROM issue_comments WHERE issue_key = ? LIMIT 10", (source_key,)
        ):
            if crow[0] and target_key in crow[0]:
                return True
    except sqlite3.OperationalError:
        pass
    return False


# ── Core rebuild ─────────────────────────────────────────────

def _compute_chunk_sims(
    chunks_a: List[Tuple[int, List[float]]],
    chunks_b: List[Tuple[int, List[float]]],
) -> Tuple[List[float], List[Tuple[int, int, float]]]:
    """Compute pairwise similarities between two sets of chunks.

    Returns (all_sims, evidence_tuples).
    """
    all_sims: List[float] = []
    evidence: List[Tuple[int, int, float]] = []
    for idx_a, vec_a in chunks_a:
        for idx_b, vec_b in chunks_b:
            sim = node_cosine(vec_a, vec_b)
            all_sims.append(sim)
            evidence.append((idx_a, idx_b, sim))
    evidence.sort(key=lambda x: x[2], reverse=True)
    return all_sims, evidence


def rebuild_soft_edges(workspace_path: Path, graph: Graph) -> int:
    """Rebuild all derived edges. Returns count of edges added.

    Pipeline:
    1. Remove all existing derived edges
    2. Load signals (embeddings, enrichments)
    3. For each candidate pair, compute confidence for each edge type
    4. Prune to enforce max out-degree and density limits
    5. Return count of edges added (graph is mutated in-place)
    """
    # Phase 0: remove previous derived edges
    removed = graph.remove_edges_by_origin("derived")
    if removed:
        logger.info("Removed %d previous derived edges", removed)

    db_path = workspace_path / "app" / "jarvis.db"
    if not db_path.exists():
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        return _rebuild_with_conn(conn, graph, workspace_path)
    finally:
        conn.close()


def _rebuild_with_conn(conn: sqlite3.Connection, graph: Graph, workspace_path: Path) -> int:
    """Inner rebuild logic with an open connection."""
    _conn = conn  # local alias for nested closures

    # Load all signals
    node_embeds = _load_node_embeddings(conn)
    chunk_embeds = _load_chunk_embeddings(conn)
    enrichments = _load_enrichments(conn)
    hard_index = _build_hard_edge_index(graph)

    # Collect enrichable node IDs (issues + notes that have embeddings or enrichments)
    enrichable_nodes: List[str] = []
    for node_id in graph.nodes:
        if node_id.startswith("issue:") or node_id.startswith("note:"):
            enrichable_nodes.append(node_id)

    if len(enrichable_nodes) < 2:
        return 0

    # Pre-compute lookups
    enrich_map: Dict[str, Dict[str, Any]] = {}
    for nid in enrichable_nodes:
        ekey = _node_id_to_enrichment_key(nid)
        if ekey and ekey in enrichments:
            enrich_map[nid] = enrichments[ekey]

    candidate_edges: List[Edge] = []

    for i in range(len(enrichable_nodes)):
        node_a = enrichable_nodes[i]
        vec_a = node_embeds.get(node_a)
        path_a = _node_id_to_path(node_a)
        chunks_a = chunk_embeds.get(path_a, []) if path_a else []
        enrich_a = enrich_map.get(node_a, {})

        for j in range(i + 1, len(enrichable_nodes)):
            node_b = enrichable_nodes[j]
            vec_b = node_embeds.get(node_b)
            path_b = _node_id_to_path(node_b)
            chunks_b = chunk_embeds.get(path_b, []) if path_b else []
            enrich_b = enrich_map.get(node_b, {})

            # Pre-compute shared signals
            n_sim = node_cosine(vec_a, vec_b) if (vec_a and vec_b) else 0.0
            chunk_sims, chunk_evidence = (
                _compute_chunk_sims(chunks_a, chunks_b) if (chunks_a and chunks_b) else ([], [])
            )
            kw_a = enrich_a.get("keywords", [])
            kw_b = enrich_b.get("keywords", [])
            kw_jacc = keyword_jaccard(kw_a, kw_b)

            area_a = enrich_a.get("business_area", "")
            area_b = enrich_b.get("business_area", "")
            risk_a = enrich_a.get("risk_level", "")
            risk_b = enrich_b.get("risk_level", "")

            # ── same_topic_as (symmetric) ──
            topic_conf = confidence_same_topic(n_sim, chunk_sims, kw_jacc)
            if topic_conf >= CONFIDENCE_FLOORS[EDGE_SAME_TOPIC]:
                top_evidence = tuple(chunk_evidence[:3]) if chunk_evidence else ()
                candidate_edges.append(Edge(
                    source=node_a, target=node_b, type=EDGE_SAME_TOPIC,
                    weight=round(topic_conf, 3), evidence=top_evidence, origin="derived",
                ))
                candidate_edges.append(Edge(
                    source=node_b, target=node_a, type=EDGE_SAME_TOPIC,
                    weight=round(topic_conf, 3), evidence=top_evidence, origin="derived",
                ))

            # ── same_business_area_as (symmetric) ──
            if area_a and area_b and area_a != "unknown" and area_b != "unknown":
                areas_match = area_a == area_b
                area_conf = confidence_same_business_area(areas_match, topic_conf)
                if area_conf >= CONFIDENCE_FLOORS[EDGE_SAME_AREA]:
                    # Store area name in evidence for UI tooltip
                    area_evidence = ((0, 0, area_conf),)  # placeholder evidence
                    candidate_edges.append(Edge(
                        source=node_a, target=node_b, type=EDGE_SAME_AREA,
                        weight=round(area_conf, 3), evidence=area_evidence, origin="derived",
                    ))
                    candidate_edges.append(Edge(
                        source=node_b, target=node_a, type=EDGE_SAME_AREA,
                        weight=round(area_conf, 3), evidence=area_evidence, origin="derived",
                    ))

            # ── same_risk_cluster_as (symmetric) ──
            if area_a and area_b and risk_a and risk_b:
                same_cluster = (area_a == area_b and risk_a == risk_b
                                and area_a != "unknown" and risk_a not in ("", "unknown"))
                risk_conf = confidence_same_risk_cluster(same_cluster, topic_conf)
                if risk_conf >= CONFIDENCE_FLOORS[EDGE_SAME_RISK]:
                    candidate_edges.append(Edge(
                        source=node_a, target=node_b, type=EDGE_SAME_RISK,
                        weight=round(risk_conf, 3), origin="derived",
                    ))
                    candidate_edges.append(Edge(
                        source=node_b, target=node_a, type=EDGE_SAME_RISK,
                        weight=round(risk_conf, 3), origin="derived",
                    ))

            # ── likely_dependency_on (directed, both directions checked) ──
            for src, tgt in ((node_a, node_b), (node_b, node_a)):
                has_hard = (src, tgt, "blocks") in hard_index or (src, tgt, "depends_on") in hard_index
                has_ref = _find_forward_references(src, tgt, graph, _conn)
                dep_conf = confidence_likely_dependency(has_ref, topic_conf, has_hard)
                if dep_conf >= CONFIDENCE_FLOORS[EDGE_LIKELY_DEP]:
                    candidate_edges.append(Edge(
                        source=src, target=tgt, type=EDGE_LIKELY_DEP,
                        weight=round(dep_conf, 3), origin="derived",
                    ))

            # ── implementation_of_same_problem (symmetric) ──
            high_chunk_pairs = [s for s in chunk_sims if s >= 0.80]
            best_chunk = max(chunk_sims) if chunk_sims else 0.0
            same_area = (area_a == area_b and area_a != "" and area_a != "unknown")
            prob_conf = confidence_same_problem(len(high_chunk_pairs), same_area, best_chunk)
            if prob_conf >= CONFIDENCE_FLOORS[EDGE_SAME_PROBLEM]:
                top_evidence = tuple(chunk_evidence[:3]) if chunk_evidence else ()
                candidate_edges.append(Edge(
                    source=node_a, target=node_b, type=EDGE_SAME_PROBLEM,
                    weight=round(prob_conf, 3), evidence=top_evidence, origin="derived",
                ))
                candidate_edges.append(Edge(
                    source=node_b, target=node_a, type=EDGE_SAME_PROBLEM,
                    weight=round(prob_conf, 3), evidence=top_evidence, origin="derived",
                ))

    # Prune and add to graph
    pruned = _prune_edges(candidate_edges, graph)
    for edge in pruned:
        graph.edges.append(edge)

    logger.info("Added %d derived soft edges", len(pruned))
    return len(pruned)


# ── Pruning ──────────────────────────────────────────────────

def _prune_edges(candidates: List[Edge], graph: Graph) -> List[Edge]:
    """Apply pruning rules:
    1. Per node, per edge type, keep top-K by confidence.
    2. Drop edges below floor.
    3. Drop edges where a stronger hard edge exists.
    4. Drop self-loops.
    5. Density cap: if total > 5 * |nodes|, raise floors and re-prune.
    """
    # Rule 4: drop self-loops
    candidates = [e for e in candidates if e.source != e.target]

    # Rule 2: already enforced before adding to candidates, but re-check for safety
    candidates = [
        e for e in candidates
        if e.weight >= CONFIDENCE_FLOORS.get(e.type, 0.0)
    ]

    # Rule 3: drop if identical hard edge superset exists
    suppress_types = {"blocks", "depends_on", "duplicate_of"}
    hard_pairs: Set[Tuple[str, str]] = set()
    for e in graph.edges:
        if e.origin != "derived" and e.type in suppress_types:
            hard_pairs.add((e.source, e.target))
            hard_pairs.add((e.target, e.source))

    # likely_dependency_on is suppressed by hard blocks/depends_on
    candidates = [
        e for e in candidates
        if not (e.type == EDGE_LIKELY_DEP and (e.source, e.target) in hard_pairs)
    ]

    # Rule 1: enforce max out-degree per node per edge type
    candidates = _enforce_max_out_degree(candidates)

    # Rule 5: density cap
    node_count = max(len(graph.nodes), 1)
    max_derived = DENSITY_MULTIPLIER * node_count

    if len(candidates) > max_derived:
        candidates = _apply_density_cap(candidates, max_derived)

    return candidates


def _enforce_max_out_degree(edges: List[Edge]) -> List[Edge]:
    """Keep top-K edges per (source, type) by weight."""
    # Group by (source, type)
    groups: Dict[Tuple[str, str], List[Edge]] = {}
    for e in edges:
        key = (e.source, e.type)
        groups.setdefault(key, []).append(e)

    result: List[Edge] = []
    for (source, etype), group in groups.items():
        max_k = MAX_OUT_DEGREE.get(etype, 8)
        # Sort by weight descending, stable tie-break on target id
        group.sort(key=lambda e: (-e.weight, e.target))
        result.extend(group[:max_k])

    return result


def _apply_density_cap(edges: List[Edge], max_count: int) -> List[Edge]:
    """Raise all floors by +0.05 increments until edges fit within cap."""
    current = list(edges)
    for _ in range(20):  # Safety limit
        if len(current) <= max_count:
            break
        # Raise all floors
        raised_floors = {k: v + FLOOR_RAISE_STEP for k, v in CONFIDENCE_FLOORS.items()}
        current = [e for e in current if e.weight >= raised_floors.get(e.type, 0.0)]
        current = _enforce_max_out_degree(current)
    return current
