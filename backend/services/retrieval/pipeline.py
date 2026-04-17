"""Hybrid retrieval pipeline combining BM25, cosine similarity, graph scoring,
and (optionally) enrichment facet matching.

Each signal contributes a normalized [0,1] score. Weights are re-normalized
when a signal is unavailable so the pipeline degrades gracefully. Results
include a ``_signals`` dict for transparency/debugging.

Step 22f adds:
- Enrichment match signal (weight 0.15 when active)
- Post-fusion boosts for explicit keys, sprint, blockers
- Facet pre-filtering on the issue candidate set
- Feature-gated via JARVIS_FEATURE_JIRA_RETRIEVAL=1
"""

import json
import logging
import os
from typing import Dict, List, Optional, Set

from services import graph_service, memory_service
from services.retrieval.intent import FacetFilter, QueryIntent
from services.retrieval.intent_parser import parse_intent

logger = logging.getLogger(__name__)

# Default fusion weights (rebalanced for chunk signal — step 20e)
WEIGHT_BM25 = 0.25
WEIGHT_COSINE = 0.40
WEIGHT_GRAPH = 0.35

# Jira-aware weights (step 22f) — enrichment signal takes 0.15
WEIGHT_BM25_JIRA = 0.22
WEIGHT_COSINE_JIRA = 0.33
WEIGHT_GRAPH_JIRA = 0.30
WEIGHT_ENRICHMENT = 0.15

# Post-fusion boosts (step 22f)
BOOST_EXPLICIT_KEY = 0.30
BOOST_BLOCKER_WORKING_SET = 0.10
BOOST_SPRINT_ACTIVE = 0.05
BOOST_CAP = 0.40

# Semantic anchor matching thresholds (step 20b)
_ANCHOR_SIMILARITY_THRESHOLD = 0.50
_MAX_SEMANTIC_ANCHORS = 5


def _is_jira_retrieval_enabled() -> bool:
    """Check if Jira-aware retrieval is feature-gated on."""
    return os.environ.get("JARVIS_FEATURE_JIRA_RETRIEVAL") == "1"


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


# ── Enrichment signal (step 22f) ──────────────────────────────────


async def _load_enrichments_for_paths(
    paths: List[str],
    workspace_path=None,
) -> Dict[str, Dict]:
    """Load latest enrichment payloads for a batch of note paths.

    Returns {path: enrichment_payload_dict}.
    """
    if not paths:
        return {}

    import aiosqlite

    db_p = memory_service._db_path(workspace_path)
    if not db_p.exists():
        return {}

    result: Dict[str, Dict] = {}
    async with aiosqlite.connect(str(db_p)) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in paths)
        cursor = await db.execute(
            f"""
            SELECT subject_id, payload
            FROM latest_enrichment
            WHERE subject_type = 'jira_issue'
              AND subject_id IN ({placeholders})
            """,
            paths,
        )
        rows = await cursor.fetchall()
        for row in rows:
            try:
                result[row["subject_id"]] = json.loads(row["payload"])
            except (json.JSONDecodeError, TypeError):
                continue
    return result


def _compute_enrichment_score(
    enrichment: Optional[Dict],
    intent: QueryIntent,
) -> float:
    """Score a candidate based on enrichment facet match against intent."""
    if not enrichment:
        return 0.0

    score = 0.0
    if intent.business_area_hint and enrichment.get("business_area") == intent.business_area_hint:
        score += 0.5
    if intent.risk_hint == "high-risk" and enrichment.get("risk_level") == "high":
        score += 0.3
    if intent.risk_hint == "unclear" and enrichment.get("ambiguity_level") == "unclear":
        score += 0.2

    return min(score, 1.0)


async def _apply_facet_filter(
    candidates: Dict[str, Dict],
    facets: FacetFilter,
    workspace_path=None,
) -> Dict[str, Dict]:
    """Apply hard facet filters to narrow the candidate set.

    Non-issue candidates are always kept (unless wants_issues_only).
    Only issue candidates are filtered by facet values from frontmatter.
    """
    if facets.is_empty:
        return candidates

    import aiosqlite

    db_p = memory_service._db_path(workspace_path)
    if not db_p.exists():
        return candidates

    # Find which candidates are issues (in jira/ folder)
    issue_paths = [p for p in candidates if p.startswith("jira/")]
    if not issue_paths:
        return candidates

    # Load frontmatter for issue candidates
    async with aiosqlite.connect(str(db_p)) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in issue_paths)
        cursor = await db.execute(
            f"SELECT path, frontmatter FROM notes WHERE path IN ({placeholders})",
            issue_paths,
        )
        rows = await cursor.fetchall()

    fm_map: Dict[str, Dict] = {}
    for row in rows:
        try:
            fm_map[row["path"]] = json.loads(row["frontmatter"])
        except (json.JSONDecodeError, TypeError):
            fm_map[row["path"]] = {}

    filtered = {}
    for path, data in candidates.items():
        # Non-issue candidates pass through
        if not path.startswith("jira/"):
            filtered[path] = data
            continue

        fm = fm_map.get(path, {})
        if not _matches_facets(fm, facets):
            continue
        filtered[path] = data

    return filtered


def _matches_facets(frontmatter: Dict, facets: FacetFilter) -> bool:
    """Check if a note's frontmatter matches all specified facet values."""
    if facets.status_category:
        val = frontmatter.get("status_category", "")
        if val not in facets.status_category:
            return False

    if facets.sprint_state:
        # "active" sprint check — we look at whether the issue has any sprint
        # with state matching. Since frontmatter stores sprint name only,
        # we treat any sprinted issue as "active" for now.
        if "active" in facets.sprint_state:
            sprint = frontmatter.get("sprint", "")
            if not sprint:
                return False

    if facets.sprint_name:
        sprints = frontmatter.get("sprints", [])
        if not any(s in facets.sprint_name for s in sprints):
            return False

    if facets.assignee:
        assignee = frontmatter.get("assignee", "")
        if assignee not in facets.assignee:
            return False

    if facets.project_key:
        pk = frontmatter.get("project_key", "")
        if pk not in facets.project_key:
            return False

    if facets.business_area or facets.risk_level or facets.ambiguity_level or facets.work_type:
        # These require enrichment data — skip frontmatter-only filtering
        # (enrichment signal handles scoring for these)
        pass

    return True


def _compute_post_fusion_boost(
    path: str,
    intent: QueryIntent,
    enrichment: Optional[Dict],
) -> float:
    """Compute additive boost after fusion. Capped at BOOST_CAP."""
    boost = 0.0

    # Explicit key boost
    if intent.keys_in_query:
        fm_key = _extract_issue_key_from_path(path)
        if fm_key and fm_key in intent.keys_in_query:
            boost += BOOST_EXPLICIT_KEY

    # Sprint active boost
    if intent.sprint_filter == "active" and path.startswith("jira/"):
        boost += BOOST_SPRINT_ACTIVE

    return min(boost, BOOST_CAP)


def _extract_issue_key_from_path(path: str) -> Optional[str]:
    """Extract issue key from path like 'jira/PROJ/PROJ-123.md'."""
    import re
    m = re.search(r"([A-Z][A-Z0-9]{1,9}-\d{1,6})\.md$", path)
    return m.group(1) if m else None


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
    """Hybrid retrieval combining BM25, chunk cosine similarity and graph scoring.

    When ``JARVIS_FEATURE_JIRA_RETRIEVAL=1`` is set, also runs intent
    parsing, enrichment scoring, facet filtering, and post-fusion boosts.
    """
    intent, results = await retrieve_with_intent(query, limit=limit, workspace_path=workspace_path)
    return results


async def retrieve_with_intent(
    query: str,
    limit: int = 5,
    workspace_path=None,
    facets_override: Optional[FacetFilter] = None,
) -> tuple:
    """Full retrieval returning both ``(QueryIntent, results)``."""
    if not query or not query.strip():
        return QueryIntent(text=query or ""), []

    jira_enabled = _is_jira_retrieval_enabled()

    # Parse intent (always — cheap and deterministic)
    intent = parse_intent(query)

    # Merge explicit facet overrides from API
    if facets_override and not facets_override.is_empty:
        intent.facets = facets_override

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
            "_enrichment": 0.0,
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
                                    "_enrichment": 0.0,
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
                                        "_enrichment": 0.0,
                                        "_best_chunk": None,
                                        "_best_section": None,
                                    }
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("Cosine retrieval failed: %s", exc)

    if not candidate_pool:
        return intent, []

    # --- Facet pre-filter (step 22f) ---
    if jira_enabled and intent.has_jira_signals and not intent.facets.is_empty:
        candidate_pool = await _apply_facet_filter(
            candidate_pool, intent.facets, workspace_path,
        )
        if not candidate_pool:
            return intent, []

    # Filter to issues only when intent demands it
    if jira_enabled and intent.wants_issues_only:
        issue_candidates = {
            p: d for p, d in candidate_pool.items() if p.startswith("jira/")
        }
        # Only restrict if we have issues — otherwise fall back to all
        if issue_candidates:
            candidate_pool = issue_candidates

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

    # --- Signal 4: Enrichment match (step 22f, gated) ---
    enrichment_available = False
    enrichments: Dict[str, Dict] = {}
    if jira_enabled and intent.has_jira_signals:
        issue_paths = [p for p in candidate_pool if p.startswith("jira/")]
        if issue_paths:
            enrichments = await _load_enrichments_for_paths(
                issue_paths, workspace_path,
            )
            if enrichments:
                enrichment_available = True
                for path in issue_paths:
                    if path in candidate_pool:
                        candidate_pool[path]["_enrichment"] = _compute_enrichment_score(
                            enrichments.get(path), intent,
                        )

    # --- Weighted fusion ---
    if jira_enabled and enrichment_available:
        w_bm25 = WEIGHT_BM25_JIRA
        w_cos = WEIGHT_COSINE_JIRA if cosine_available else 0.0
        w_graph = WEIGHT_GRAPH_JIRA if graph else 0.0
        w_enrich = WEIGHT_ENRICHMENT
    else:
        w_bm25 = WEIGHT_BM25
        w_cos = WEIGHT_COSINE if cosine_available else 0.0
        w_graph = WEIGHT_GRAPH if graph else 0.0
        w_enrich = 0.0

    total_w = w_bm25 + w_cos + w_graph + w_enrich or 1.0
    w_bm25 /= total_w
    w_cos /= total_w
    w_graph /= total_w
    w_enrich /= total_w

    scored: List[Dict] = []
    for path, data in candidate_pool.items():
        fused = (
            w_bm25 * data["_bm25"]
            + w_cos * data["_cosine"]
            + w_graph * data["_graph"]
            + w_enrich * data.get("_enrichment", 0.0)
        )

        # Post-fusion boosts (step 22f)
        boost = 0.0
        if jira_enabled and intent.has_jira_signals:
            boost = _compute_post_fusion_boost(path, intent, enrichments.get(path))

        final = fused + boost

        signals = {
            "bm25": round(data["_bm25"], 3),
            "cosine": round(data["_cosine"], 3),
            "graph": round(data["_graph"], 3),
        }
        if enrichment_available:
            signals["enrichment"] = round(data.get("_enrichment", 0.0), 3)
        if boost > 0:
            signals["boost"] = round(boost, 3)

        scored.append({
            **data,
            "_score": final,
            "_signals": signals,
        })

    # Sort by fused score; tie-breaker: recency
    scored.sort(
        key=lambda x: (x["_score"], x.get("updated_at", "")),
        reverse=True,
    )

    # --- Signal 5: Cross-encoder reranker (precision pass) ---------------
    # Take top-N hybrid candidates and re-score with a local cross-encoder.
    # Disable with JARVIS_DISABLE_RERANKER=1.  Falls back silently if the
    # reranker model is unavailable.
    rerank_enabled = os.environ.get("JARVIS_DISABLE_RERANKER") != "1"
    if rerank_enabled and len(scored) > 1:
        try:
            from services.reranker_service import rerank as _rerank
            from services.reranker_service import is_available as _rr_available

            if _rr_available():
                # Cap the rerank pool to keep latency bounded (~50-150ms).
                rerank_pool_size = int(os.environ.get("JARVIS_RERANKER_POOL", "20"))
                pool = scored[:rerank_pool_size]
                # Build the document text used by the cross-encoder.
                # Prefer the best chunk text (most query-aligned); fall back
                # to title + folder when no chunk text is available.
                docs: List[str] = []
                for d in pool:
                    text = d.get("_best_chunk") or ""
                    if not text:
                        title = d.get("title", "")
                        folder = d.get("folder", "")
                        text = f"{title} ({folder})".strip()
                    docs.append(text[:2000])  # cap to keep encoder fast

                rerank_scores = _rerank(query, docs)
                if rerank_scores is not None and len(rerank_scores) == len(pool):
                    # Normalise rerank scores to [0,1] within the pool, then
                    # blend 70% rerank + 30% original fused score.  This keeps
                    # some signal from BM25/cosine/graph in case the reranker
                    # is over-confident on a single token match.
                    lo = min(rerank_scores)
                    hi = max(rerank_scores)
                    span = (hi - lo) or 1.0
                    rerank_weight = float(os.environ.get("JARVIS_RERANKER_WEIGHT", "0.7"))
                    rerank_weight = max(0.0, min(1.0, rerank_weight))

                    for d, raw in zip(pool, rerank_scores):
                        norm = (raw - lo) / span
                        d["_rerank"] = round(float(raw), 4)
                        d["_score"] = (
                            rerank_weight * norm
                            + (1.0 - rerank_weight) * d["_score"]
                        )
                        sig = d.get("_signals", {})
                        sig["rerank"] = round(norm, 3)
                        d["_signals"] = sig

                    # Resort the pool with new blended scores; the tail
                    # (beyond rerank_pool_size) keeps its original order.
                    pool.sort(
                        key=lambda x: (x["_score"], x.get("updated_at", "")),
                        reverse=True,
                    )
                    scored = pool + scored[rerank_pool_size:]
        except Exception as exc:
            logger.warning("Reranker pass skipped: %s", exc)

    result = _cluster_dedup(scored, limit)

    # Clean internal fields but KEEP _best_chunk and _best_section for context_builder
    for r in result:
        r.pop("_score", None)
        r.pop("_bm25", None)
        r.pop("_cosine", None)
        r.pop("_graph", None)
        r.pop("_enrichment", None)
        r.pop("_rerank", None)
        r.pop("_bm25_score", None)
        r.pop("_node_id", None)

    return intent, result
