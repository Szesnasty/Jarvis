"""Local cross-encoder reranker.

Uses fastembed's TextCrossEncoder to re-score retrieval candidates with a
multilingual reranker model.  100% local, no API calls — same trust model
as embedding_service.

Default model: ``jinaai/jina-reranker-v2-base-multilingual`` (~1.1 GB).
Override via ``JARVIS_RERANKER_MODEL`` env var.  Disable entirely via
``JARVIS_DISABLE_RERANKER=1``.

The reranker is a *cross-encoder*: it scores each (query, document) pair
together, which is far more precise than the bi-encoder cosine score —
but slower (~50-150 ms per query for 20 candidates on CPU).  We use it
only for the final precision pass over the top-N hybrid candidates.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# --- Model configuration ----------------------------------------------------
DEFAULT_MODEL = "jinaai/jina-reranker-v2-base-multilingual"
_FALLBACK_MODEL = "Xenova/ms-marco-MiniLM-L-12-v2"  # tiny + English-friendly

# Singleton model instance (lazy-loaded)
_model = None
_model_name: Optional[str] = None


def is_disabled() -> bool:
    """Honour user opt-out."""
    return os.environ.get("JARVIS_DISABLE_RERANKER") == "1"


def _resolve_model_name() -> str:
    return os.environ.get("JARVIS_RERANKER_MODEL", DEFAULT_MODEL)


def _get_model():
    """Lazy-load reranker on first use.  Returns None if unavailable."""
    global _model, _model_name
    if _model is not None:
        return _model
    if is_disabled():
        return None

    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError:
        logger.info("fastembed reranker unavailable (TextCrossEncoder not importable)")
        return None

    name = _resolve_model_name()
    try:
        logger.info("Loading reranker model %s ...", name)
        _model = TextCrossEncoder(model_name=name)
        _model_name = name
        logger.info("Reranker model loaded.")
        return _model
    except Exception as exc:
        logger.warning(
            "Reranker model %s failed to load (%s); trying fallback %s",
            name, exc, _FALLBACK_MODEL,
        )
        try:
            _model = TextCrossEncoder(model_name=_FALLBACK_MODEL)
            _model_name = _FALLBACK_MODEL
            logger.info("Fallback reranker %s loaded.", _FALLBACK_MODEL)
            return _model
        except Exception as exc2:
            logger.warning("Fallback reranker also failed: %s", exc2)
            _model = None
            return None


def is_available() -> bool:
    """Cheap probe — does NOT load the model unless already loaded."""
    if is_disabled():
        return False
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # noqa: F401
    except ImportError:
        return False
    return True


def model_name() -> Optional[str]:
    """Return the active reranker model name (loads if needed)."""
    _get_model()
    return _model_name


def rerank(
    query: str,
    documents: List[str],
) -> Optional[List[float]]:
    """Score each document against *query* with the cross-encoder.

    Returns a list of float scores aligned with *documents*, or ``None``
    if the reranker is unavailable (caller should fall back to original
    ordering).  Higher score = more relevant.
    """
    if not query or not documents:
        return None
    model = _get_model()
    if model is None:
        return None
    try:
        scores = list(model.rerank(query, documents))
        return [float(s) for s in scores]
    except Exception as exc:
        logger.warning("Reranker scoring failed: %s", exc)
        return None


def rerank_pairs(
    query: str,
    items: List[Tuple[str, str]],
) -> Optional[List[Tuple[str, float]]]:
    """Convenience: rerank a list of ``(id, document_text)`` pairs.

    Returns a list of ``(id, score)`` sorted by descending score, or
    ``None`` if the reranker is unavailable.
    """
    if not items:
        return []
    docs = [text for _, text in items]
    scores = rerank(query, docs)
    if scores is None:
        return None
    paired = [(item_id, score) for (item_id, _), score in zip(items, scores)]
    paired.sort(key=lambda x: x[1], reverse=True)
    return paired
