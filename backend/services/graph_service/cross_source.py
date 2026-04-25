"""Cross-source linking & intra-file chunk connections.

Step 22e: widens the chunk-linker to any chunked subject and layers
enrichment signals on top.  Produces derived edges that cross source
type boundaries (note→issue, issue→decision, etc.) and intra-file
edges for long documents.

All edges carry ``origin="cross_source"`` or ``origin="intra_file"``
and are fully rebuildable from inputs alone.
"""

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.graph_service.models import Edge, Graph
from services.graph_service.soft_edges import node_cosine, top_k_mean

logger = logging.getLogger(__name__)

# ── Edge catalogue ───────────────────────────────────────────

EDGE_MENTIONS_ISSUE = "mentions_issue"
EDGE_MENTIONED_IN_NOTE = "mentioned_in_note"
EDGE_IMPLEMENTS_DECISION = "implements_decision"
EDGE_DERIVED_FROM_RESEARCH = "derived_from_research"
EDGE_ABOUT_SAME_TOPIC = "about_same_topic_as"
EDGE_SAME_DOCUMENT_THREAD = "same_document_thread"

CONFIDENCE_FLOORS: Dict[str, float] = {
    EDGE_MENTIONS_ISSUE: 0.90,         # high — regex/link match
    EDGE_MENTIONED_IN_NOTE: 0.90,
    EDGE_IMPLEMENTS_DECISION: 0.70,
    EDGE_DERIVED_FROM_RESEARCH: 0.68,
    EDGE_ABOUT_SAME_TOPIC: 0.60,
    EDGE_SAME_DOCUMENT_THREAD: 0.80,
}

MAX_OUT_DEGREE: Dict[str, int] = {
    EDGE_MENTIONS_ISSUE: 8,
    EDGE_MENTIONED_IN_NOTE: 8,
    EDGE_IMPLEMENTS_DECISION: 5,
    EDGE_DERIVED_FROM_RESEARCH: 5,
    EDGE_ABOUT_SAME_TOPIC: 8,
    EDGE_SAME_DOCUMENT_THREAD: 3,
}

# Density cap: cross_source edges ≤ 4 * |nodes|
DENSITY_MULTIPLIER = 4

# ── Enrichment compatibility table ───────────────────────────
# (source_exec_type, target_exec_type) → (edge_type, bias)
# Documented and unit-tested.

ENRICHMENT_COMPAT: List[Tuple[str, str, str, float]] = [
    # (source_exec, target_exec, edge_type, bias)
    ("investigation", "implementation", EDGE_DERIVED_FROM_RESEARCH, +0.10),
    ("decision",      "implementation", EDGE_IMPLEMENTS_DECISION,   +0.10),
]

AREA_MATCH_BONUS = 0.05      # same business_area on both sides
AREA_MISMATCH_PENALTY = -0.10  # different business_area → strong negative

# ── Issue key regex ──────────────────────────────────────────

_ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
_WIKI_LINK_RE = re.compile(r"\[\[([A-Z][A-Z0-9]+-\d+)\]\]")


# ── Data loading helpers ─────────────────────────────────────

def _load_node_embeddings(conn: sqlite3.Connection) -> Dict[str, List[float]]:
    from services.embedding_service import blob_to_vector
    result: Dict[str, List[float]] = {}
    try:
        for row in conn.execute("SELECT node_id, embedding FROM node_embeddings"):
            result[row[0]] = blob_to_vector(row[1])
    except sqlite3.OperationalError:
        pass
    return result


def _load_chunk_embeddings(conn: sqlite3.Connection) -> Dict[str, List[Tuple[int, List[float]]]]:
    from services.embedding_service import blob_to_vector
    result: Dict[str, List[Tuple[int, List[float]]]] = {}
    try:
        for row in conn.execute("SELECT path, chunk_index, embedding FROM chunk_embeddings"):
            result.setdefault(row[0], []).append((row[1], blob_to_vector(row[2])))
    except sqlite3.OperationalError:
        pass
    return result


def _load_enrichments(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    try:
        for row in conn.execute(
            "SELECT subject_type, subject_id, payload FROM latest_enrichment"
        ):
            key = "%s:%s" % (row[0], row[1])
            try:
                result[key] = json.loads(row[2] or "{}")
            except json.JSONDecodeError:
                pass
    except sqlite3.OperationalError:
        pass
    return result


def _load_canonical_entities(conn: sqlite3.Connection) -> Dict[str, Set[str]]:
    """Load canonical entity IDs per note path from entity_aliases + graph.

    Returns {path: {canonical_id, ...}}.
    """
    # We use the graph's mentions edges to map paths → entity IDs,
    # but we also look for aliases table entries.
    result: Dict[str, Set[str]] = {}
    try:
        # From note_chunks, get all paths
        for row in conn.execute(
            "SELECT DISTINCT path FROM note_chunks"
        ):
            result.setdefault(row[0], set())
    except sqlite3.OperationalError:
        pass
    return result


def _load_issue_keys(conn: sqlite3.Connection) -> Set[str]:
    """Load all known issue keys from the issues table."""
    keys: Set[str] = set()
    try:
        for row in conn.execute("SELECT issue_key FROM issues"):
            keys.add(row[0])
    except sqlite3.OperationalError:
        pass
    return keys


def _load_note_bodies(conn: sqlite3.Connection) -> Dict[str, str]:
    """Load note path → body for scanning for issue key references."""
    result: Dict[str, str] = {}
    try:
        for row in conn.execute("SELECT path, body FROM notes WHERE body IS NOT NULL AND body != ''"):
            result[row[0]] = row[1]
    except sqlite3.OperationalError:
        pass
    return result


def _load_issue_note_paths(conn: sqlite3.Connection) -> Dict[str, str]:
    """Map issue_key → note_path from the issues table."""
    result: Dict[str, str] = {}
    try:
        for row in conn.execute("SELECT issue_key, note_path FROM issues"):
            result[row[0]] = row[1]
    except sqlite3.OperationalError:
        pass
    return result


# ── Pairwise chunk similarity ───────────────────────────────

def _compute_chunk_sims(
    chunks_a: List[Tuple[int, List[float]]],
    chunks_b: List[Tuple[int, List[float]]],
    max_pairs: int = 20,
) -> Tuple[List[float], List[Tuple[int, int, float]]]:
    """Compute pairwise similarities between two sets of chunks.

    Limits computation to top-``max_pairs`` chunk pairs (by descending
    similarity in source chunk) to bound cost.

    Returns (all_sims, evidence_tuples_sorted_desc).
    """
    all_sims: List[float] = []
    evidence: List[Tuple[int, int, float]] = []

    # Cap chunk sets if very large (reservoir sample would be ideal but
    # truncation is simpler and sufficient for now)
    a_set = chunks_a[:300]
    b_set = chunks_b[:300]

    for idx_a, vec_a in a_set:
        for idx_b, vec_b in b_set:
            sim = node_cosine(vec_a, vec_b)
            all_sims.append(sim)
            evidence.append((idx_a, idx_b, sim))

    evidence.sort(key=lambda x: x[2], reverse=True)
    evidence = evidence[:max_pairs]
    return all_sims, evidence


# ── Enrichment compatibility ────────────────────────────────

def enrichment_compatibility(
    enrich_a: Dict[str, Any],
    enrich_b: Dict[str, Any],
) -> Dict[str, float]:
    """Compute enrichment-based biases for each edge type.

    Returns {edge_type: bias_value}.
    """
    biases: Dict[str, float] = {}

    exec_a = enrich_a.get("execution_type", "unknown")
    exec_b = enrich_b.get("execution_type", "unknown")
    area_a = enrich_a.get("business_area", "unknown")
    area_b = enrich_b.get("business_area", "unknown")

    # Directional enrichment compatibility
    for src_exec, tgt_exec, edge_type, bias in ENRICHMENT_COMPAT:
        if exec_a == src_exec and exec_b == tgt_exec:
            biases[edge_type] = biases.get(edge_type, 0.0) + bias
        if exec_b == src_exec and exec_a == tgt_exec:
            biases[edge_type] = biases.get(edge_type, 0.0) + bias

    # Area match/mismatch bonus for about_same_topic_as
    if area_a != "unknown" and area_b != "unknown":
        if area_a == area_b:
            biases[EDGE_ABOUT_SAME_TOPIC] = biases.get(EDGE_ABOUT_SAME_TOPIC, 0.0) + AREA_MATCH_BONUS
        else:
            biases[EDGE_ABOUT_SAME_TOPIC] = biases.get(EDGE_ABOUT_SAME_TOPIC, 0.0) + AREA_MISMATCH_PENALTY

    return biases


# ── Confidence formulas ──────────────────────────────────────

def confidence_about_same_topic(
    node_sim: float,
    chunk_sims: List[float],
    shared_entity_count: int,
    enrichment_bias: float = 0.0,
) -> float:
    """Cross-source about_same_topic_as.

    Requires ≥ 2 chunk matches ≥ 0.78 AND ≥ 1 shared canonical entity.
    """
    high_chunk_pairs = sum(1 for s in chunk_sims if s >= 0.78)
    if high_chunk_pairs < 2 or shared_entity_count < 1:
        return 0.0

    base = (
        0.50 * node_sim
        + 0.35 * top_k_mean(chunk_sims, k=3)
        + 0.15 * min(shared_entity_count / 3.0, 1.0)
    )
    return min(max(base + enrichment_bias, 0.0), 1.0)


def confidence_implements_decision(
    chunk_sims: List[float],
    enrichment_bias: float = 0.0,
) -> float:
    """issue → decision: ≥ 2 chunk matches ≥ 0.78 AND enrichment execution_type=implementation."""
    high_chunk_pairs = sum(1 for s in chunk_sims if s >= 0.78)
    if high_chunk_pairs < 2:
        return 0.0
    base = 0.60 + 0.30 * top_k_mean(chunk_sims, k=3)
    return min(max(base + enrichment_bias, 0.0), 1.0)


def confidence_derived_from_research(
    chunk_sims: List[float],
    enrichment_bias: float = 0.0,
) -> float:
    """issue → note: ≥ 2 chunk matches ≥ 0.75 AND enrichment execution_type=investigation on note side."""
    high_chunk_pairs = sum(1 for s in chunk_sims if s >= 0.75)
    if high_chunk_pairs < 2:
        return 0.0
    base = 0.55 + 0.35 * top_k_mean(chunk_sims, k=3)
    return min(max(base + enrichment_bias, 0.0), 1.0)


# ── Direct mention detection ────────────────────────────────

def find_issue_mentions_in_note(
    note_body: str,
    known_issue_keys: Set[str],
) -> List[str]:
    """Find issue keys mentioned in a note body (wiki-links or bare keys).

    Only returns keys that exist in the known_issue_keys set.
    """
    found: Set[str] = set()

    # Wiki-links: [[ONB-142]]
    for m in _WIKI_LINK_RE.finditer(note_body):
        key = m.group(1)
        if key in known_issue_keys:
            found.add(key)

    # Bare keys: ONB-142 in text
    for m in _ISSUE_KEY_RE.finditer(note_body):
        key = m.group(1)
        if key in known_issue_keys:
            found.add(key)

    return sorted(found)


# ── Node-id helpers ──────────────────────────────────────────

def _node_to_path(node_id: str) -> Optional[str]:
    """Extract the chunk-embedding path from a node ID."""
    if node_id.startswith("note:"):
        return node_id[5:]
    if node_id.startswith("issue:"):
        # issue nodes are keyed by issue_key; their MD lives at jira/{PROJECT}/{KEY}.md
        return None  # looked up via _issue_note_paths
    return None


def _node_to_enrichment_key(node_id: str) -> Optional[str]:
    if node_id.startswith("issue:"):
        return "jira_issue:%s" % node_id[6:]
    if node_id.startswith("note:"):
        return "note:%s" % node_id[5:]
    return None


def _node_subject_type(node_id: str, graph: Graph) -> str:
    """Return the subject type string for a node."""
    node = graph.nodes.get(node_id)
    if not node:
        return "unknown"
    nt = node.type
    if nt == "note":
        return "note"
    if nt == "jira_issue":
        return "jira_issue"
    return nt


def _get_entities_for_node(
    node_id: str,
    graph: Graph,
) -> Set[str]:
    """Get the set of canonical entity IDs connected to a node via mentions edges."""
    entities: Set[str] = set()
    for e in graph.edges:
        if e.type == "mentions":
            if e.source == node_id:
                entities.add(e.target)
            elif e.target == node_id:
                entities.add(e.source)
    return entities


# ── Intra-file edges ─────────────────────────────────────────

def _build_intra_file_edges(
    chunk_embeds: Dict[str, List[Tuple[int, List[float]]]],
    min_chunks: int = 8,
    distance_threshold: int = 3,
    similarity_floor: float = 0.72,
    max_per_chunk: int = 5,
    max_chunks_per_doc: int = 400,
) -> List[Edge]:
    """Build same_document_thread edges within long files.

    Connects chunks ``(i, j)`` where ``|i - j| >= distance_threshold`` and
    ``cosine >= similarity_floor``. Limited to ``max_per_chunk`` outbound
    edges per chunk.

    Implementation notes
    --------------------
    Long documents (e.g. PDF-extracted papers) can contain thousands of
    chunks; the previous Python loop did ~3765² = 14M cosines per paper
    and timed out. We now:

    * Stride-sample to ``max_chunks_per_doc`` if a doc exceeds it.
    * Stack vectors into a normalised matrix and compute the full
      pairwise sim matrix with one ``M @ M.T`` numpy call.
    * Mask the lower triangle (forward direction only) and the
      neighbour-distance band (``|i - j| < distance_threshold``).

    Threshold lowered from 0.80 → 0.72 because diverse-vocabulary
    sections of one paper (intro vs experiments vs related work) often
    cap below 0.80 yet are clearly the same document thread. A more
    permissive floor combined with a per-chunk top-K cap (5 instead of
    3) makes intra-file structure visible without flooding the graph.
    """
    import numpy as np

    edges: List[Edge] = []

    for path, chunks in chunk_embeds.items():
        if len(chunks) <= min_chunks:
            continue

        chunks_sorted = sorted(chunks, key=lambda c: c[0])
        if len(chunks_sorted) > max_chunks_per_doc:
            step = len(chunks_sorted) / max_chunks_per_doc
            chunks_sorted = [chunks_sorted[int(i * step)] for i in range(max_chunks_per_doc)]

        indices = np.array([c[0] for c in chunks_sorted], dtype=np.int64)
        vecs = np.array([c[1] for c in chunks_sorted], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        unit = vecs / norms

        sims = unit @ unit.T  # (n, n) cosine matrix

        # Forward direction only + distance band → mask out the rest
        n = sims.shape[0]
        ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        idx_diff = np.abs(indices[ii] - indices[jj])
        keep = (jj > ii) & (idx_diff >= distance_threshold) & (sims >= similarity_floor)

        if not keep.any():
            continue

        # Per-row top-K by similarity (max_per_chunk outbound edges/chunk)
        for row in range(n):
            row_keep = np.where(keep[row])[0]
            if row_keep.size == 0:
                continue
            row_sims = sims[row, row_keep]
            order = np.argsort(-row_sims)[:max_per_chunk]
            src_idx = int(indices[row])
            src_id = "note:%s" % path
            for k in order:
                target_idx = int(indices[int(row_keep[k])])
                sim = float(row_sims[int(k)])
                evidence = ((src_idx, target_idx, round(sim, 3)),)
                edges.append(Edge(
                    source=src_id, target=src_id,
                    type=EDGE_SAME_DOCUMENT_THREAD,
                    weight=round(sim, 3),
                    evidence=evidence,
                    origin="intra_file",
                ))

    return edges


# ── Pruning ──────────────────────────────────────────────────

def _enforce_max_out_degree(edges: List[Edge]) -> List[Edge]:
    """Keep top-K edges per (source, type) by weight."""
    groups: Dict[Tuple[str, str], List[Edge]] = {}
    for e in edges:
        key = (e.source, e.type)
        groups.setdefault(key, []).append(e)

    result: List[Edge] = []
    for (source, etype), group in groups.items():
        max_k = MAX_OUT_DEGREE.get(etype, 8)
        group.sort(key=lambda e: (-e.weight, e.target))
        result.extend(group[:max_k])
    return result


def _prune_edges(candidates: List[Edge], graph: Graph) -> List[Edge]:
    """Prune candidate cross-source edges."""
    # Drop self-loops (same node, not intra-file)
    candidates = [
        e for e in candidates
        if e.source != e.target or e.type == EDGE_SAME_DOCUMENT_THREAD
    ]

    # Drop below floors
    candidates = [
        e for e in candidates
        if e.weight >= CONFIDENCE_FLOORS.get(e.type, 0.0)
    ]

    # Enforce max out-degree
    candidates = _enforce_max_out_degree(candidates)

    # Density cap
    node_count = max(len(graph.nodes), 1)
    max_edges = DENSITY_MULTIPLIER * node_count
    if len(candidates) > max_edges:
        # Raise floors iteratively
        current = list(candidates)
        for _ in range(20):
            if len(current) <= max_edges:
                break
            current = [e for e in current if e.weight >= CONFIDENCE_FLOORS.get(e.type, 0.0) + 0.05]
            current = _enforce_max_out_degree(current)
        candidates = current

    return candidates


# ── Core rebuild ─────────────────────────────────────────────

def rebuild_cross_source_edges(workspace_path: Path, graph: Graph) -> int:
    """Rebuild all cross-source and intra-file edges.

    Returns count of edges added.  Graph is mutated in-place.
    """
    # Phase 0: remove previous cross_source and intra_file edges
    removed_cs = graph.remove_edges_by_origin("cross_source")
    removed_if = graph.remove_edges_by_origin("intra_file")
    if removed_cs or removed_if:
        logger.info(
            "Removed %d cross-source + %d intra-file edges",
            removed_cs, removed_if,
        )

    db_path = workspace_path / "app" / "jarvis.db"
    if not db_path.exists():
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        return _rebuild_with_conn(conn, graph, workspace_path)
    finally:
        conn.close()


def _rebuild_with_conn(
    conn: sqlite3.Connection,
    graph: Graph,
    workspace_path: Path,
) -> int:
    """Inner rebuild logic."""
    # Load all signals
    node_embeds = _load_node_embeddings(conn)
    chunk_embeds = _load_chunk_embeddings(conn)
    enrichments = _load_enrichments(conn)
    known_issue_keys = _load_issue_keys(conn)
    note_bodies = _load_note_bodies(conn)
    issue_note_paths = _load_issue_note_paths(conn)

    candidate_edges: List[Edge] = []

    # ── Phase 1: Direct mention edges (deterministic, no embeddings) ──
    _emit_mention_edges(
        graph, note_bodies, known_issue_keys, candidate_edges,
    )

    # ── Phase 2: Cross-type semantic edges ──
    _emit_cross_type_semantic_edges(
        graph, node_embeds, chunk_embeds, enrichments,
        issue_note_paths, candidate_edges,
    )

    # ── Phase 3: Intra-file edges ──
    intra_edges = _build_intra_file_edges(chunk_embeds)
    candidate_edges.extend(intra_edges)

    # Prune and add to graph
    pruned = _prune_edges(candidate_edges, graph)
    for edge in pruned:
        graph.edges.append(edge)

    logger.info(
        "Added %d cross-source edges (%d mention, %d semantic, %d intra-file)",
        len(pruned),
        sum(1 for e in pruned if e.type in (EDGE_MENTIONS_ISSUE, EDGE_MENTIONED_IN_NOTE)),
        sum(1 for e in pruned if e.type in (EDGE_ABOUT_SAME_TOPIC, EDGE_IMPLEMENTS_DECISION, EDGE_DERIVED_FROM_RESEARCH)),
        sum(1 for e in pruned if e.type == EDGE_SAME_DOCUMENT_THREAD),
    )
    return len(pruned)


# ── Phase 1: Mention edges ──────────────────────────────────

def _emit_mention_edges(
    graph: Graph,
    note_bodies: Dict[str, str],
    known_issue_keys: Set[str],
    candidate_edges: List[Edge],
) -> None:
    """Emit mentions_issue / mentioned_in_note edges from text references."""
    for note_path, body in note_bodies.items():
        note_node_id = "note:%s" % note_path
        if note_node_id not in graph.nodes:
            continue

        mentioned_keys = find_issue_mentions_in_note(body, known_issue_keys)
        for issue_key in mentioned_keys:
            issue_node_id = "issue:%s" % issue_key
            if issue_node_id not in graph.nodes:
                continue

            # note → issue
            candidate_edges.append(Edge(
                source=note_node_id,
                target=issue_node_id,
                type=EDGE_MENTIONS_ISSUE,
                weight=0.95,
                origin="cross_source",
            ))
            # issue → note (reverse)
            candidate_edges.append(Edge(
                source=issue_node_id,
                target=note_node_id,
                type=EDGE_MENTIONED_IN_NOTE,
                weight=0.95,
                origin="cross_source",
            ))


# ── Phase 2: Cross-type semantic edges ──────────────────────

def _emit_cross_type_semantic_edges(
    graph: Graph,
    node_embeds: Dict[str, List[float]],
    chunk_embeds: Dict[str, List[Tuple[int, List[float]]]],
    enrichments: Dict[str, Dict[str, Any]],
    issue_note_paths: Dict[str, str],
    candidate_edges: List[Edge],
) -> None:
    """Emit semantic cross-type edges between notes and issues."""
    # Collect enrichable nodes that straddle source types
    notes: List[str] = []
    issues: List[str] = []
    for node_id, node in graph.nodes.items():
        if node.type == "note":
            notes.append(node_id)
        elif node.type == "jira_issue":
            issues.append(node_id)

    if not notes or not issues:
        return

    # Pre-compute enrichment map
    enrich_map: Dict[str, Dict[str, Any]] = {}
    for nid in notes + issues:
        ekey = _node_to_enrichment_key(nid)
        if ekey and ekey in enrichments:
            enrich_map[nid] = enrichments[ekey]

    # Build path lookup for issues
    issue_paths: Dict[str, str] = {}
    for node_id in issues:
        issue_key = node_id[6:]
        if issue_key in issue_note_paths:
            issue_paths[node_id] = issue_note_paths[issue_key]

    # Entity sets per node (from graph mentions edges)
    entity_cache: Dict[str, Set[str]] = {}

    def get_entities(nid: str) -> Set[str]:
        if nid not in entity_cache:
            entity_cache[nid] = _get_entities_for_node(nid, graph)
        return entity_cache[nid]

    # ANN top-K simulation: for each issue, find top-K most similar notes
    # by node embedding (capped at 40 per spec)
    ANN_TOP_K = 40

    for issue_id in issues:
        vec_issue = node_embeds.get(issue_id)
        path_issue = issue_paths.get(issue_id)
        chunks_issue = chunk_embeds.get(path_issue, []) if path_issue else []
        enrich_issue = enrich_map.get(issue_id, {})

        # Rank notes by node-level similarity
        scored_notes: List[Tuple[str, float]] = []
        for note_id in notes:
            vec_note = node_embeds.get(note_id)
            if vec_issue and vec_note:
                sim = node_cosine(vec_issue, vec_note)
                scored_notes.append((note_id, sim))
            else:
                scored_notes.append((note_id, 0.0))

        scored_notes.sort(key=lambda x: x[1], reverse=True)
        top_notes = scored_notes[:ANN_TOP_K]

        for note_id, n_sim in top_notes:
            if n_sim < 0.30:
                continue  # too dissimilar, skip

            path_note = _node_to_path(note_id)
            chunks_note = chunk_embeds.get(path_note, []) if path_note else []
            enrich_note = enrich_map.get(note_id, {})

            # Pre-compute shared signals
            chunk_sims, chunk_ev = (
                _compute_chunk_sims(chunks_issue, chunks_note)
                if (chunks_issue and chunks_note) else ([], [])
            )

            shared_entities = get_entities(issue_id) & get_entities(note_id)
            compat_biases = enrichment_compatibility(enrich_issue, enrich_note)

            # ── about_same_topic_as (cross-type, symmetric) ──
            topic_bias = compat_biases.get(EDGE_ABOUT_SAME_TOPIC, 0.0)
            topic_conf = confidence_about_same_topic(
                n_sim, chunk_sims, len(shared_entities), topic_bias,
            )
            if topic_conf >= CONFIDENCE_FLOORS[EDGE_ABOUT_SAME_TOPIC]:
                top_evidence = tuple(chunk_ev[:3]) if chunk_ev else ()
                candidate_edges.append(Edge(
                    source=issue_id, target=note_id,
                    type=EDGE_ABOUT_SAME_TOPIC,
                    weight=round(topic_conf, 3),
                    evidence=top_evidence,
                    origin="cross_source",
                ))
                candidate_edges.append(Edge(
                    source=note_id, target=issue_id,
                    type=EDGE_ABOUT_SAME_TOPIC,
                    weight=round(topic_conf, 3),
                    evidence=top_evidence,
                    origin="cross_source",
                ))

            # ── implements_decision (issue → decision note) ──
            impl_bias = compat_biases.get(EDGE_IMPLEMENTS_DECISION, 0.0)
            exec_issue = enrich_issue.get("execution_type", "")
            exec_note = enrich_note.get("execution_type", "")
            if exec_issue == "implementation" and exec_note == "decision":
                impl_conf = confidence_implements_decision(chunk_sims, impl_bias)
                if impl_conf >= CONFIDENCE_FLOORS[EDGE_IMPLEMENTS_DECISION]:
                    top_evidence = tuple(chunk_ev[:3]) if chunk_ev else ()
                    candidate_edges.append(Edge(
                        source=issue_id, target=note_id,
                        type=EDGE_IMPLEMENTS_DECISION,
                        weight=round(impl_conf, 3),
                        evidence=top_evidence,
                        origin="cross_source",
                    ))

            # ── derived_from_research (issue → note) ──
            research_bias = compat_biases.get(EDGE_DERIVED_FROM_RESEARCH, 0.0)
            if exec_note == "investigation":
                research_conf = confidence_derived_from_research(
                    chunk_sims, research_bias,
                )
                if research_conf >= CONFIDENCE_FLOORS[EDGE_DERIVED_FROM_RESEARCH]:
                    top_evidence = tuple(chunk_ev[:3]) if chunk_ev else ()
                    candidate_edges.append(Edge(
                        source=issue_id, target=note_id,
                        type=EDGE_DERIVED_FROM_RESEARCH,
                        weight=round(research_conf, 3),
                        evidence=top_evidence,
                        origin="cross_source",
                    ))
