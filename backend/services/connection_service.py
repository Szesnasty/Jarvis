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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SuggestedLink(BaseModel):
    path: str
    confidence: float
    methods: List[str]
    tier: str = "normal"  # "strong" | "normal" | "weak"
    evidence: Optional[str] = None


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
# Orchestrator
# ---------------------------------------------------------------------------


async def connect_note(
    note_path: str,
    workspace_path: Optional[Path] = None,
    mode: str = "fast",
) -> ConnectionResult:
    """Run the per-note Smart Connect pipeline.

    Steps:
      1. Read note + build connection query.
      2. Generate candidates from BM25 + note/chunk embeddings.
      3. Score, prune, cap.
      4. Write ``suggested_related`` to frontmatter.
      5. Incrementally update the graph (no full rebuild).

    ``mode`` is currently advisory — ``"aggressive"`` keeps weak
    suggestions; ``"fast"`` (default) drops them. Aggressive mode is
    used by the semantic-orphan repair path (PR 5).
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
        # Empty notes get an empty suggestion block but still update the graph.
        return await _finalise(note_path, ws, fm, body, full_path, [])

    bm25_scores = await _bm25_signal(query, note_path, ws, list_notes)
    note_emb_scores: Dict[str, float] = {}
    chunk_emb_scores: Dict[str, Tuple[float, Optional[str]]] = {}

    if os.environ.get("JARVIS_DISABLE_EMBEDDINGS") != "1":
        note_emb_scores, chunk_emb_scores = await _embedding_signals(query, note_path, ws)

    merged = _merge_candidates(
        bm25_scores=bm25_scores,
        note_emb_scores=note_emb_scores,
        chunk_emb_scores=chunk_emb_scores,
        mode=mode,
    )
    kept = enforce_caps(merged, _folder_of(note_path))
    suggested = [
        SuggestedLink(
            path=p,
            confidence=score,
            methods=methods,
            tier=tier,
            evidence=evidence,
        )
        for (p, score, methods, evidence, tier) in kept
    ]
    return await _finalise(note_path, ws, fm, body, full_path, suggested)


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
    mode: str,
) -> List[Tuple[str, float, List[str], Optional[str], str]]:
    """Combine signals into per-candidate scores.

    The base formula in :func:`score_candidate` assumes all signals fire.
    When some sources are unavailable (e.g. embeddings disabled, chunks
    missing for a short note), the score is divided by the sum of weights
    of *active* signals so a single strong signal can still cross the
    floor. This is graceful degradation, not weight inflation: a perfect
    BM25 hit with nothing else still maxes at 1.0 of the BM25-only space.
    """
    active_weight_sum = 0.0
    if bm25_scores:
        active_weight_sum += W_BM25
    if note_emb_scores:
        active_weight_sum += W_NOTE_EMB
    if chunk_emb_scores:
        active_weight_sum += W_CHUNK_EMB
    if active_weight_sum <= 0.0:
        return []

    paths = set(bm25_scores) | set(note_emb_scores) | set(chunk_emb_scores)
    out: List[Tuple[str, float, List[str], Optional[str], str]] = []

    for path in paths:
        b = bm25_scores.get(path, 0.0)
        ne = note_emb_scores.get(path, 0.0)
        ce_score, ce_section = chunk_emb_scores.get(path, (0.0, None))

        raw = score_candidate(bm25=b, note_emb=ne, chunk_emb=ce_score)
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

        evidence = f"Matched section: {ce_section}" if ce_section else None
        out.append((path, round(score, 3), methods, evidence, tier))

    out.sort(key=lambda item: item[1], reverse=True)
    return out


async def _finalise(
    note_path: str,
    ws: Path,
    fm: Dict,
    body: str,
    full_path: Path,
    suggested: List[SuggestedLink],
) -> ConnectionResult:
    fm["suggested_related"] = [
        {
            "path": s.path,
            "confidence": s.confidence,
            "methods": s.methods,
            **({"evidence": s.evidence} if s.evidence else {}),
        }
        for s in suggested
    ]
    full_path.write_text(add_frontmatter(body, fm), encoding="utf-8")

    try:
        from services.graph_service import ingest_note as graph_ingest_note

        graph_ingest_note(note_path, workspace_path=ws)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("connect_note graph ingest failed: %s", exc)

    return ConnectionResult(
        note_path=note_path,
        suggested=suggested,
        strong_count=sum(1 for s in suggested if s.tier == "strong"),
    )
