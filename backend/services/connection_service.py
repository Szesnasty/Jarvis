"""Smart Connect — per-note ingest-time linking (Step 25, PR 1).

Cheap, deterministic candidate generation that runs on every note ingest.
Uses signals already produced by the indexing pipeline:

  * BM25 over ``notes_fts`` (via :func:`memory_service.list_notes`)
  * Note-level cosine similarity (via :func:`embedding_service.search_similar`)
  * Chunk-level cosine similarity (via :func:`embedding_service.search_similar_chunks`)

The result is written to the note's frontmatter as ``suggested_related`` and
the graph is updated incrementally via :func:`graph_service.ingest_note`.
No global ``rebuild_graph()``, no LLM calls.

Aliases, entity overlap and dismissals are added in later PRs of step 25.
"""

from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from utils.markdown import add_frontmatter, parse_frontmatter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables (kept module-level so tests can monkeypatch and the spec stays in sync)
# ---------------------------------------------------------------------------

CONNECTION_QUERY_MAX_CHARS = 800
DEFAULT_BM25_LIMIT = 15
DEFAULT_NOTE_EMB_LIMIT = 10
DEFAULT_CHUNK_EMB_LIMIT = 10

SCORE_FLOOR = 0.45
SCORE_NORMAL = 0.60
SCORE_STRONG = 0.80
NEAR_DUPLICATE_SCORE = 0.92

MAX_SUGGESTIONS = 5
MAX_SAME_FOLDER = 2
MAX_NEAR_DUPLICATES = 1

# Score weights (must sum to 1.0). Aliases/entities/source are kept here
# so PR 4/5 can supply non-zero inputs without changing the formula.
W_BM25 = 0.30
W_NOTE_EMB = 0.30
W_CHUNK_EMB = 0.20
W_ENTITY = 0.10
W_ALIAS = 0.07
W_SOURCE = 0.03

# Bumping this constant causes the next backfill to re-visit notes that were
# processed at a lower version, without requiring force=True.
CURRENT_SMART_CONNECT_VERSION = 2


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SuggestedLink(BaseModel):
    path: str
    confidence: float
    methods: List[str]
    tier: str = "normal"  # "strong" | "normal" | "weak"
    evidence: Optional[str] = None
    suggested_by: Optional[str] = None


class EntityCounts(BaseModel):
    people: int = 0
    organizations: int = 0
    projects: int = 0
    places: int = 0


class ConnectionResult(BaseModel):
    note_path: str
    suggested: List[SuggestedLink] = Field(default_factory=list)
    strong_count: int = 0
    aliases_matched: List[str] = Field(default_factory=list)
    entities: EntityCounts = Field(default_factory=EntityCounts)
    graph_edges_added: int = 0


@dataclass
class _SuggestContext:
    """Intermediate result passed from generate_suggestions to apply_suggestions."""
    note_path: str
    ws: "Path"
    fm: Dict
    body: str
    full_path: "Path"
    suggestions: List[SuggestedLink]
    aliases_matched: List[str]
    mode: str


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without a workspace)
# ---------------------------------------------------------------------------


def _clamp(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def score_candidate(
    bm25: float = 0.0,
    note_emb: float = 0.0,
    chunk_emb: float = 0.0,
    entity: float = 0.0,
    alias: float = 0.0,
    same_source: float = 0.0,
) -> float:
    """Combine normalised signals into a single ``[0, 1]`` confidence.

    All inputs must already be normalised against their own candidate set.
    The function is monotonic in each input — raising any signal can only
    raise the score (verified in :mod:`tests.test_connection_service_scoring`).
    """
    return (
        W_BM25 * _clamp(bm25)
        + W_NOTE_EMB * _clamp(note_emb)
        + W_CHUNK_EMB * _clamp(chunk_emb)
        + W_ENTITY * _clamp(entity)
        + W_ALIAS * _clamp(alias)
        + W_SOURCE * _clamp(same_source)
    )


def tier_for(score: float) -> str:
    """Map a confidence score to ``strong | normal | weak | drop``."""
    if score >= SCORE_STRONG:
        return "strong"
    if score >= SCORE_NORMAL:
        return "normal"
    if score >= SCORE_FLOOR:
        return "weak"
    return "drop"


_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def build_connection_query(fm: Dict, body: str) -> str:
    """Build the candidate-generation query: title + headings + tags + snippet."""
    title = str(fm.get("title", "") or "")
    tags = " ".join(str(t) for t in fm.get("tags", []) or [])
    headings = " ".join(_HEADING_RE.findall(body))
    snippet = body[:CONNECTION_QUERY_MAX_CHARS]
    parts = [p for p in (title, headings, tags, snippet) if p]
    return "\n".join(parts).strip()


def _folder_of(path: str) -> str:
    return str(Path(path).parent) if "/" in path else ""


def enforce_caps(
    candidates: List[Tuple[str, float, List[str], Optional[str], str]],
    source_folder: str,
) -> List[Tuple[str, float, List[str], Optional[str], str]]:
    """Apply per-note caps: total, same-folder, near-duplicate.

    ``candidates`` must be sorted by score descending. Tuple shape:
    ``(path, score, methods, evidence, tier)``.

    Near-duplicates are candidates whose total confidence is ``>=``
    :data:`NEAR_DUPLICATE_SCORE`. They are likely to be the same content
    indexed twice; we keep at most :data:`MAX_NEAR_DUPLICATES` of them.
    """
    kept: List[Tuple[str, float, List[str], Optional[str], str]] = []
    folder_counts: Dict[str, int] = defaultdict(int)
    near_dup_count = 0

    for cand in candidates:
        path, score, _methods, _evidence, _tier = cand
        cand_folder = _folder_of(path)

        is_near_dup = score >= NEAR_DUPLICATE_SCORE
        if is_near_dup and near_dup_count >= MAX_NEAR_DUPLICATES:
            continue
        if (
            cand_folder
            and cand_folder == source_folder
            and folder_counts[cand_folder] >= MAX_SAME_FOLDER
        ):
            continue

        kept.append(cand)
        folder_counts[cand_folder] += 1
        if is_near_dup:
            near_dup_count += 1
        if len(kept) >= MAX_SUGGESTIONS:
            break
    return kept


# ---------------------------------------------------------------------------
# Orchestrator — public API
# ---------------------------------------------------------------------------


async def generate_suggestions(
    note_path: str,
    workspace_path: Optional[Path] = None,
    mode: str = "fast",
) -> "_SuggestContext":
    """Pure read: load note, compute all signals, return candidates without writing.

    Strictly read-only — does NOT mutate frontmatter, graph JSON, alias_index,
    dismissed_suggestions, connection_events, related, or suggested_related.
    Must NOT lazily create missing embeddings.
    """
    from config import get_settings
    from services.memory_service import _validate_path, list_notes

    ws = workspace_path or get_settings().workspace_path
    mem = ws / "memory"
    _validate_path(note_path, mem)
    full_path = mem / note_path
    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")

    content = full_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(content)
    query = build_connection_query(fm, body)

    if not query:
        return _SuggestContext(
            note_path=note_path, ws=ws, fm=fm, body=body,
            full_path=full_path, suggestions=[], aliases_matched=[], mode=mode,
        )

    bm25_scores = await _bm25_signal(query, note_path, ws, list_notes)
    note_emb_scores: Dict[str, float] = {}
    chunk_emb_scores: Dict[str, Tuple[float, Optional[str]]] = {}

    if os.environ.get("JARVIS_DISABLE_EMBEDDINGS") != "1":
        note_emb_scores, chunk_emb_scores = await _embedding_signals(query, note_path, ws)

    alias_scores, aliases_matched = _alias_signal(note_path, fm, body, ws)

    # Drop dismissed pairs so they never participate in scoring or capping.
    dismissed = _dismissed_targets_for(note_path, ws)
    if dismissed:
        for d in dismissed:
            bm25_scores.pop(d, None)
            note_emb_scores.pop(d, None)
            chunk_emb_scores.pop(d, None)
            alias_scores.pop(d, None)

    merged = _merge_candidates(
        bm25_scores=bm25_scores,
        note_emb_scores=note_emb_scores,
        chunk_emb_scores=chunk_emb_scores,
        alias_scores=alias_scores,
        mode=mode,
    )
    kept = enforce_caps(merged, _folder_of(note_path))

    # Semantic orphan repair: retry in aggressive mode to surface weak suggestions.
    if (
        mode == "fast"
        and not any(item[4] in ("strong", "normal") for item in kept)
        and _is_semantic_orphan_safe(note_path, ws)
    ):
        merged = _merge_candidates(
            bm25_scores=bm25_scores,
            note_emb_scores=note_emb_scores,
            chunk_emb_scores=chunk_emb_scores,
            alias_scores=alias_scores,
            mode="aggressive",
        )
        kept = enforce_caps(merged, _folder_of(note_path))

    suggested_by = f"smart_connect_v{CURRENT_SMART_CONNECT_VERSION}"
    suggestions = [
        SuggestedLink(
            path=p,
            confidence=score,
            methods=methods,
            tier=tier,
            evidence=evidence,
            suggested_by=suggested_by,
        )
        for (p, score, methods, evidence, tier) in kept
    ]
    return _SuggestContext(
        note_path=note_path, ws=ws, fm=fm, body=body,
        full_path=full_path, suggestions=suggestions,
        aliases_matched=aliases_matched, mode=mode,
    )


async def apply_suggestions(
    ctx: "_SuggestContext",
    min_confidence: Optional[float] = None,
) -> ConnectionResult:
    """Write suggestions to frontmatter, update graph, emit edges.

    Filters by ``min_confidence`` when provided: only suggestions at or above
    the threshold are written to the note. Useful for conservative bulk runs.
    """
    to_write = ctx.suggestions
    if min_confidence is not None:
        to_write = [s for s in to_write if s.confidence >= min_confidence]
    return await _finalise(
        ctx.note_path, ctx.ws, ctx.fm, ctx.body, ctx.full_path, to_write,
        aliases_matched=ctx.aliases_matched,
        mode=ctx.mode,
    )


async def connect_note(
    note_path: str,
    workspace_path: Optional[Path] = None,
    mode: str = "fast",
    *,
    dry_run: bool = False,
    min_confidence: Optional[float] = None,
) -> ConnectionResult:
    """Run the per-note Smart Connect pipeline.

    When ``dry_run=True``, returns suggestions but does NOT write frontmatter,
    graph JSON, alias_index, dismissed_suggestions, or connection_events.
    """
    ctx = await generate_suggestions(note_path, workspace_path=workspace_path, mode=mode)
    if dry_run:
        return ConnectionResult(
            note_path=ctx.note_path,
            suggested=ctx.suggestions,
            strong_count=sum(1 for s in ctx.suggestions if s.tier == "strong"),
            aliases_matched=ctx.aliases_matched,
            graph_edges_added=0,
        )
    return await apply_suggestions(ctx, min_confidence=min_confidence)


def _is_semantic_orphan_safe(note_path: str, ws: Path) -> bool:
    """Best-effort orphan check; never raises into the ingest path."""
    try:
        from services.graph_service import is_semantic_orphan
        return is_semantic_orphan(note_path, workspace_path=ws)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("semantic orphan check failed: %s", exc)
        return False


def _dismissed_targets_for(note_path: str, ws: Path) -> set:
    """Return the set of target paths the user has dismissed for this note."""
    try:
        from services.dismissed_suggestions import list_dismissed_for
        from services.memory_service import _db_path
        return list_dismissed_for(_db_path(ws), note_path)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("dismissed_suggestions lookup failed: %s", exc)
        return set()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _bm25_signal(
    query: str,
    note_path: str,
    ws: Path,
    list_notes_fn,
) -> Dict[str, float]:
    """Return ``{path: normalised_bm25_score}`` excluding the note itself."""
    try:
        # list_notes truncates to 8 word tokens internally; passing the full
        # query is fine and lets it pick the most informative tokens.
        hits = await list_notes_fn(
            search=query[:400],
            limit=DEFAULT_BM25_LIMIT,
            workspace_path=ws,
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("connect_note BM25 step failed: %s", exc)
        return {}

    raw: Dict[str, float] = {}
    for hit in hits:
        path = hit.get("path")
        if not path or path == note_path:
            continue
        raw[path] = abs(float(hit.get("_bm25_score", 0.0)))

    if not raw:
        return {}
    max_score = max(raw.values()) or 1.0
    return {p: s / max_score for p, s in raw.items()}


async def _embedding_signals(
    query: str,
    note_path: str,
    ws: Path,
) -> Tuple[Dict[str, float], Dict[str, Tuple[float, Optional[str]]]]:
    """Return note-level and chunk-level normalised similarity scores."""
    note_scores: Dict[str, float] = {}
    chunk_scores: Dict[str, Tuple[float, Optional[str]]] = {}

    try:
        from services.embedding_service import search_similar, search_similar_chunks
    except Exception as exc:  # pragma: no cover
        logger.warning("connect_note embedding import failed: %s", exc)
        return note_scores, chunk_scores

    try:
        note_hits = await search_similar(
            query, limit=DEFAULT_NOTE_EMB_LIMIT, workspace_path=ws,
        )
        max_n = max((s for p, s in note_hits if p != note_path), default=0.0)
        for path, sim in note_hits:
            if path == note_path:
                continue
            note_scores[path] = (sim / max_n) if max_n > 0 else 0.0
    except Exception as exc:  # pragma: no cover
        logger.warning("connect_note note-embedding step failed: %s", exc)

    try:
        chunk_hits = await search_similar_chunks(
            query, limit=DEFAULT_CHUNK_EMB_LIMIT, workspace_path=ws,
        )
        max_c = max(
            (h["best_chunk_score"] for h in chunk_hits if h.get("path") != note_path),
            default=0.0,
        )
        for hit in chunk_hits:
            path = hit.get("path")
            if not path or path == note_path:
                continue
            score = hit.get("best_chunk_score", 0.0)
            norm = (score / max_c) if max_c > 0 else 0.0
            chunk_scores[path] = (norm, hit.get("best_chunk_section"))
    except Exception as exc:  # pragma: no cover
        logger.warning("connect_note chunk-embedding step failed: %s", exc)

    return note_scores, chunk_scores


def _merge_candidates(
    bm25_scores: Dict[str, float],
    note_emb_scores: Dict[str, float],
    chunk_emb_scores: Dict[str, Tuple[float, Optional[str]]],
    alias_scores: Optional[Dict[str, Tuple[float, str]]] = None,
    mode: str = "fast",
) -> List[Tuple[str, float, List[str], Optional[str], str]]:
    """Combine signals into per-candidate scores.

    The base formula in :func:`score_candidate` assumes all signals fire.
    When some sources are unavailable (e.g. embeddings disabled, chunks
    missing for a short note), the score is divided by the sum of weights
    of *active* signals so a single strong signal can still cross the
    floor. This is graceful degradation, not weight inflation: a perfect
    BM25 hit with nothing else still maxes at 1.0 of the BM25-only space.
    """
    alias_scores = alias_scores or {}
    active_weight_sum = 0.0
    if bm25_scores:
        active_weight_sum += W_BM25
    if note_emb_scores:
        active_weight_sum += W_NOTE_EMB
    if chunk_emb_scores:
        active_weight_sum += W_CHUNK_EMB
    if alias_scores:
        active_weight_sum += W_ALIAS
    if active_weight_sum <= 0.0:
        return []

    paths = (
        set(bm25_scores)
        | set(note_emb_scores)
        | set(chunk_emb_scores)
        | set(alias_scores)
    )
    out: List[Tuple[str, float, List[str], Optional[str], str]] = []

    for path in paths:
        b = bm25_scores.get(path, 0.0)
        ne = note_emb_scores.get(path, 0.0)
        ce_score, ce_section = chunk_emb_scores.get(path, (0.0, None))
        al_score, al_phrase = alias_scores.get(path, (0.0, ""))

        raw = score_candidate(
            bm25=b, note_emb=ne, chunk_emb=ce_score, alias=al_score,
        )
        score = raw / active_weight_sum
        tier = tier_for(score)
        if tier == "drop":
            continue
        if tier == "weak" and mode != "aggressive":
            continue

        methods: List[str] = []
        if b > 0:
            methods.append("bm25")
        if ne > 0:
            methods.append("note_embedding")
        if ce_score > 0:
            methods.append("chunk_embedding")
        if al_score > 0:
            methods.append("alias")

        evidence: Optional[str] = None
        if al_phrase:
            evidence = f"Alias hit: {al_phrase}"
        elif ce_section:
            evidence = f"Matched section: {ce_section}"
        out.append((path, round(score, 3), methods, evidence, tier))

    out.sort(key=lambda item: item[1], reverse=True)
    return out


def _alias_signal(
    note_path: str,
    fm: Dict,
    body: str,
    ws: Path,
) -> Tuple[Dict[str, Tuple[float, str]], List[str]]:
    """Look up alias_index hits for ``body`` and return normalised scores.

    Returns ``({path: (alias_score, phrase)}, aliases_matched)``.
    Score is binary 1.0 — exact alias matches don't have a meaningful
    intensity; the W_ALIAS weight controls their contribution.
    """
    try:
        from services.alias_index import scan_body
        from services.memory_service import _db_path
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("connect_note alias import failed: %s", exc)
        return {}, []

    db_p = _db_path(ws)
    try:
        # Search title + headings + first 800 chars (same as connection query
        # body, but we include only the body — title/headings of the new note
        # itself are already in fm).
        title_text = str(fm.get("title", "") or "")
        scan_text = "\n".join(filter(None, [title_text, body[:CONNECTION_QUERY_MAX_CHARS]]))
        hits = scan_body(db_p, scan_text, exclude_path=note_path)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("connect_note alias scan failed: %s", exc)
        return {}, []

    by_path: Dict[str, Tuple[float, str]] = {}
    matched: List[str] = []
    for hit in hits:
        path = hit["path"]
        phrase = str(hit.get("phrase", ""))
        prev = by_path.get(path)
        if prev is None or len(phrase) > len(prev[1]):
            by_path[path] = (1.0, phrase)
        if phrase and phrase not in matched:
            matched.append(phrase)
    return by_path, matched


async def _finalise(
    note_path: str,
    ws: Path,
    fm: Dict,
    body: str,
    full_path: Path,
    suggested: List[SuggestedLink],
    aliases_matched: Optional[List[str]] = None,
    mode: str = "fast",
) -> ConnectionResult:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fm["smart_connect"] = {
        "version": CURRENT_SMART_CONNECT_VERSION,
        "last_run_at": now_utc,
        "last_mode": mode,
    }
    fm["suggested_related"] = [
        {
            "path": s.path,
            "confidence": s.confidence,
            "methods": s.methods,
            **({"evidence": s.evidence} if s.evidence else {}),
            **({"suggested_by": s.suggested_by} if s.suggested_by else {}),
        }
        for s in suggested
    ]
    full_path.write_text(add_frontmatter(body, fm), encoding="utf-8")

    edges_added = 0
    try:
        from services.graph_service import ingest_note as graph_ingest_note

        graph_ingest_note(note_path, workspace_path=ws)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("connect_note graph ingest failed: %s", exc)

    # Emit alias_match edges for every suggestion whose alias signal fired.
    alias_targets = [s.path for s in suggested if "alias" in s.methods]
    if alias_targets:
        edges_added += _emit_note_edges(
            note_path, [(t, "alias_match", "alias") for t in alias_targets], ws,
        )

    # Step 25 PR 5 — provenance edges from the note to its source/batch nodes.
    edges_added += _emit_provenance_edges(note_path, fm, ws)

    return ConnectionResult(
        note_path=note_path,
        suggested=suggested,
        strong_count=sum(1 for s in suggested if s.tier == "strong"),
        aliases_matched=aliases_matched or [],
        graph_edges_added=edges_added,
    )


def _emit_note_edges(
    note_path: str,
    edges: List[Tuple[str, str, str]],
    ws: Path,
) -> int:
    """Add edges of arbitrary type/origin from ``note:note_path`` to each target.

    ``edges`` is ``[(target_node_id_without_namespace_or_full_id, edge_type, origin)]``.
    Targets that look like full node IDs (contain ``:``) are kept as-is;
    otherwise they are interpreted as note paths (``note:<path>``).
    """
    try:
        from services.graph_service import load_graph, _save_and_cache
        from services.graph_service.models import _EDGE_BASE_WEIGHT
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("provenance edge import failed: %s", exc)
        return 0

    graph = load_graph(workspace_path=ws)
    if graph is None:
        return 0

    src_id = f"note:{note_path}"
    if src_id not in graph.nodes:
        graph.add_node(src_id, "note", Path(note_path).stem)

    added = 0
    for target_ref, edge_type, origin in edges:
        tgt_id = target_ref if ":" in target_ref else f"note:{target_ref}"
        if tgt_id not in graph.nodes:
            # Best-effort node bootstrap: derive type from the namespace.
            ns = tgt_id.split(":", 1)[0]
            label = tgt_id.split(":", 1)[-1]
            graph.add_node(tgt_id, ns, label)
        existing = any(
            e for e in graph.edges
            if e.source == src_id and e.target == tgt_id and e.type == edge_type
        )
        if existing:
            continue
        weight = _EDGE_BASE_WEIGHT.get(edge_type, 0.5)
        graph.add_edge(src_id, tgt_id, edge_type, weight=weight, origin=origin)
        added += 1

    if added:
        try:
            _save_and_cache(graph, workspace_path=ws)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("provenance edge save failed: %s", exc)
    return added


def _emit_provenance_edges(note_path: str, fm: Dict, ws: Path) -> int:
    """Emit ``derived_from`` and ``same_batch`` edges from the note's frontmatter.

    Source: ``fm["source"]`` (any non-empty string). Hashed to a 12-char
    sha1-based id and labelled with a human-readable kind (``url``,
    ``file``, ``jira``, ``other``).

    Batch: ``fm["batch_id"]`` (set explicitly by structured / Jira ingest
    flows when they want to group co-imported notes).
    """
    import hashlib
    edges: List[Tuple[str, str, str]] = []

    source = fm.get("source")
    if isinstance(source, str) and source.strip():
        kind = _classify_source(source)
        sid = hashlib.sha1(source.strip().encode("utf-8")).hexdigest()[:12]
        node_id = f"source:{sid}"
        # Bootstrap the source node label so it isn't just the hash.
        try:
            from services.graph_service import load_graph
            graph = load_graph(workspace_path=ws)
            if graph is not None and node_id not in graph.nodes:
                graph.add_node(node_id, "source", f"{kind}:{source[:60]}")
                from services.graph_service import _save_and_cache
                _save_and_cache(graph, workspace_path=ws)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("source node bootstrap failed: %s", exc)
        edges.append((node_id, "derived_from", "source"))

    batch_id = fm.get("batch_id")
    if isinstance(batch_id, str) and batch_id.strip():
        edges.append((f"batch:{batch_id.strip()}", "same_batch", "batch"))

    if not edges:
        return 0
    return _emit_note_edges(note_path, edges, ws)


_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _classify_source(source: str) -> str:
    s = source.strip().lower()
    if _URL_RE.match(s):
        return "url"
    if s.startswith("jira:"):
        return "jira"
    if s.endswith((".pdf", ".csv", ".xml", ".md", ".txt")):
        return "file"
    return "other"


def _emit_alias_edges(note_path: str, targets: List[str], ws: Path) -> int:
    """Backwards-compatible alias-edge helper.

    Kept for symmetry with PR 3 callers/tests; delegates to the generic
    :func:`_emit_note_edges`.
    """
    return _emit_note_edges(
        note_path, [(t, "alias_match", "alias") for t in targets], ws,
    )
