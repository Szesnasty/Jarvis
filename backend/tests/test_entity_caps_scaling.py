"""Tests for length-scaled entity caps (Step 27b)."""

from services.graph_service.entity_edges import (
    MAX_PERSONS_PER_NOTE,
    MAX_ORGS_PER_NOTE,
    MAX_PROJECTS_PER_NOTE,
    MAX_PLACES_PER_NOTE,
    compute_caps,
    compute_co_mention_cap,
)


def test_short_body_uses_base_caps():
    caps = compute_caps(500)
    assert caps["person"] == MAX_PERSONS_PER_NOTE
    assert caps["org"] == MAX_ORGS_PER_NOTE
    assert caps["project"] == MAX_PROJECTS_PER_NOTE
    assert caps["place"] == MAX_PLACES_PER_NOTE


def test_exactly_2k_uses_base_caps():
    caps = compute_caps(2_000)
    assert caps["person"] == MAX_PERSONS_PER_NOTE


def test_huge_body_clamped_to_hard_caps():
    caps = compute_caps(1_000_000)
    assert caps["person"] == 200
    assert caps["org"] == 200
    assert caps["project"] == 100
    assert caps["place"] == 100


def test_caps_scale_monotonically():
    a = compute_caps(2_000)
    b = compute_caps(10_000)
    c = compute_caps(20_000)
    d = compute_caps(40_000)
    assert a["person"] <= b["person"] <= c["person"] <= d["person"]
    assert a["org"] <= b["org"] <= c["org"] <= d["org"]


def test_caps_never_above_hard_cap():
    for body_len in (5_000, 15_000, 25_000, 35_000, 50_000, 200_000):
        caps = compute_caps(body_len)
        assert caps["person"] <= 200
        assert caps["org"] <= 200
        assert caps["project"] <= 100
        assert caps["place"] <= 100


def test_caps_never_below_base_cap():
    for body_len in (0, 100, 1_000, 2_000, 2_001, 5_000):
        caps = compute_caps(body_len)
        assert caps["person"] >= MAX_PERSONS_PER_NOTE
        assert caps["org"] >= MAX_ORGS_PER_NOTE


def test_co_mention_cap_scales():
    assert compute_co_mention_cap(500) == 100
    assert compute_co_mention_cap(2_000) == 100
    assert compute_co_mention_cap(40_000) == 400
    assert compute_co_mention_cap(1_000_000) == 400
    # Monotonic
    assert compute_co_mention_cap(10_000) <= compute_co_mention_cap(20_000)
    assert compute_co_mention_cap(20_000) <= compute_co_mention_cap(30_000)


def test_midpoint_caps_are_between_base_and_hard():
    """At ~21 KB (midpoint of scale window) caps should be roughly midway."""
    caps = compute_caps(21_000)
    # ratio ≈ 0.5, so person cap ≈ 50 + 0.5 * (200-50) = 125
    assert 100 <= caps["person"] <= 150
    assert 100 <= caps["org"] <= 150
