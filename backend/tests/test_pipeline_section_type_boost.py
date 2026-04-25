"""Tests for pipeline section-type boost (step 28d)."""
import pytest

from services.retrieval.intent import QueryIntent, FacetFilter
from services.retrieval.pipeline import (
    BOOST_SECTION_TYPE,
    BOOST_CAP,
    _compute_post_fusion_boost,
)


def _intent(preferred_section_types=None, **kwargs):
    return QueryIntent(
        text="test",
        preferred_section_types=preferred_section_types or [],
        **kwargs,
    )


def test_boost_applied_when_section_type_matches():
    """section_type in preferred_section_types → additive boost."""
    intent = _intent(preferred_section_types=["risks"])
    boost = _compute_post_fusion_boost("knowledge/doc/02-risks.md", intent, None, section_type="risks")
    assert boost == BOOST_SECTION_TYPE


def test_boost_not_applied_when_type_mismatch():
    """Different section_type → no boost."""
    intent = _intent(preferred_section_types=["risks"])
    boost = _compute_post_fusion_boost("knowledge/doc/01-intro.md", intent, None, section_type="front_matter")
    assert boost == 0.0


def test_boost_not_applied_when_section_type_absent():
    """section_type=None → no boost even when preferred types set."""
    intent = _intent(preferred_section_types=["risks"])
    boost = _compute_post_fusion_boost("knowledge/doc/01.md", intent, None, section_type=None)
    assert boost == 0.0


def test_boost_not_applied_when_no_preferred_types():
    """Empty preferred_section_types → no boost regardless of section_type."""
    intent = _intent(preferred_section_types=[])
    boost = _compute_post_fusion_boost("knowledge/doc/02.md", intent, None, section_type="risks")
    assert boost == 0.0


def test_boost_capped_at_boost_cap():
    """Combined boosts do not exceed BOOST_CAP."""
    # Use an explicit key match (0.30) + section type match (0.10)
    intent = _intent(
        preferred_section_types=["risks"],
        keys_in_query=["PROJ-1"],
    )
    boost = _compute_post_fusion_boost(
        "jira/PROJ/PROJ-1.md", intent, None, section_type="risks"
    )
    assert boost <= BOOST_CAP


def test_non_matching_candidates_not_filtered():
    """Boost does not filter — non-matching candidates get boost=0, not excluded."""
    intent = _intent(preferred_section_types=["risks"])
    candidates = [
        ("doc/risks.md", "risks"),
        ("doc/intro.md", "front_matter"),
        ("doc/reqs.md", "requirements"),
    ]
    boosts = [
        _compute_post_fusion_boost(path, intent, None, section_type=st)
        for path, st in candidates
    ]
    # Only risks should be boosted
    assert boosts[0] == BOOST_SECTION_TYPE
    assert boosts[1] == 0.0
    assert boosts[2] == 0.0
