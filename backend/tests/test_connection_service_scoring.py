"""Pure-function tests for connection_service scoring and caps (Step 25, PR 1)."""

from __future__ import annotations

import pytest

from services.connection_service import (
    MAX_NEAR_DUPLICATES,
    MAX_SAME_FOLDER,
    MAX_SUGGESTIONS,
    NEAR_DUPLICATE_SCORE,
    SCORE_FLOOR,
    SCORE_NORMAL,
    SCORE_STRONG,
    enforce_caps,
    score_candidate,
    tier_for,
)


def test_score_returns_zero_for_zero_inputs():
    assert score_candidate() == 0.0


def test_score_clamps_inputs_above_one():
    saturated = score_candidate(
        bm25=2.0, note_emb=2.0, chunk_emb=2.0,
        entity=2.0, alias=2.0, same_source=2.0,
    )
    assert saturated == pytest.approx(1.0, rel=1e-6)


def test_score_clamps_negative_inputs_to_zero():
    assert score_candidate(bm25=-1.0, note_emb=-1.0) == 0.0


def test_score_is_monotonic_in_each_signal():
    """Raising any single signal can only raise the total score."""
    base_kwargs = dict(bm25=0.4, note_emb=0.4, chunk_emb=0.4,
                       entity=0.0, alias=0.0, same_source=0.0)
    base = score_candidate(**base_kwargs)
    for signal in ("bm25", "note_emb", "chunk_emb", "entity", "alias", "same_source"):
        bumped_kwargs = dict(base_kwargs)
        bumped_kwargs[signal] = bumped_kwargs[signal] + 0.2
        bumped = score_candidate(**bumped_kwargs)
        assert bumped >= base, f"signal {signal} should not decrease score"


def test_tier_thresholds():
    assert tier_for(SCORE_STRONG) == "strong"
    assert tier_for(SCORE_NORMAL) == "normal"
    assert tier_for(SCORE_FLOOR) == "weak"
    assert tier_for(SCORE_FLOOR - 0.01) == "drop"
    assert tier_for(0.99) == "strong"
    assert tier_for(0.0) == "drop"


def _cand(path, score, methods=None, evidence=None, tier="normal"):
    return (path, score, methods or ["bm25"], evidence, tier)


def test_enforce_caps_limits_total_suggestions():
    cands = [_cand(f"knowledge/n{i}.md", 0.7 - i * 0.01) for i in range(10)]
    kept = enforce_caps(cands, source_folder="other")
    assert len(kept) == MAX_SUGGESTIONS


def test_enforce_caps_limits_same_folder():
    src_folder = "knowledge"
    cands = [
        _cand(f"{src_folder}/n{i}.md", 0.75 - i * 0.01) for i in range(5)
    ]
    kept = enforce_caps(cands, source_folder=src_folder)
    assert len(kept) == MAX_SAME_FOLDER


def test_enforce_caps_drops_extra_near_duplicates():
    """Only one candidate at or above the near-duplicate threshold is kept."""
    cands = [
        _cand("a/x.md", 0.95),  # near-dup #1, kept
        _cand("a/y.md", 0.93),  # near-dup #2, dropped
        _cand("b/z.md", 0.70),  # below threshold, kept
    ]
    kept = enforce_caps(cands, source_folder="other")
    paths = [p for p, *_ in kept]
    assert paths == ["a/x.md", "b/z.md"]
    assert len(kept) == MAX_NEAR_DUPLICATES + 1  # one near-dup + one normal


def test_enforce_caps_preserves_order():
    cands = [_cand(f"a/n{i}.md", 0.8 - i * 0.05) for i in range(4)]
    kept = enforce_caps(cands, source_folder="other")
    scores = [s for _, s, _, _, _ in kept]
    assert scores == sorted(scores, reverse=True)
