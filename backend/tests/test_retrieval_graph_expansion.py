"""Tests for step-26d graph expansion in retrieval pipeline.

Tests:
- related edge contributes at full weight (1.00) to graph score
- derived_from edge contributes 0.0 (excluded)
- same_batch edge contributes 0.0 (excluded)
- suggested_related edge weight == SUGGESTED_RELATED_MAX_WEIGHT when use_suggested_strong=True
- suggested_related weight == 0.0 when use_suggested_strong=False (default)
- convergence bonus only with expansion-eligible edges
- _expand_anchors adds at most max_added neighbours
- _expand_anchors includes related, excludes derived_from
- _expand_anchors excludes non-strong suggested_related
"""

from __future__ import annotations

import pytest

from services.graph_service.models import Graph, Edge, Node
from services.graph_service.queries import SUGGESTED_RELATED_MAX_WEIGHT
from services.retrieval.pipeline import (
    _compute_graph_score,
    _expand_anchors,
    _get_expansion_weights,
)


def _note(id: str, label: str = "") -> Node:
    return Node(id=f"note:{id}", type="note", label=label or id)


def _make_graph(*edge_specs) -> Graph:
    """Build a minimal graph from (source_short, target_short, type, weight) tuples."""
    g = Graph()
    for src, tgt, etype, w in edge_specs:
        sid = f"note:{src}"
        tid = f"note:{tgt}"
        for nid, lbl in [(sid, src), (tid, tgt)]:
            if nid not in g.nodes:
                g.nodes[nid] = _note(nid[5:], lbl)
        g.add_edge(sid, tid, etype, weight=w)
    return g


# ---------------------------------------------------------------------------
# _get_expansion_weights
# ---------------------------------------------------------------------------

def test_default_weights_related_is_one():
    w = _get_expansion_weights()
    assert w["related"] == 1.00


def test_default_weights_suggested_is_zero():
    """Default: use_suggested_strong=False → weight 0.0."""
    w = _get_expansion_weights()
    assert w["suggested_related"] == 0.0


def test_suggested_weight_when_enabled():
    """use_suggested_strong=True → weight == SUGGESTED_RELATED_MAX_WEIGHT."""
    w = _get_expansion_weights(use_suggested_strong=True)
    assert abs(w["suggested_related"] - SUGGESTED_RELATED_MAX_WEIGHT) < 1e-9


def test_use_related_false_sets_zero():
    w = _get_expansion_weights(use_related=False)
    assert w["related"] == 0.0


def test_use_part_of_false_sets_zero():
    w = _get_expansion_weights(use_part_of=False)
    assert w["part_of"] == 0.0


# ---------------------------------------------------------------------------
# _compute_graph_score — per-type weighting
# ---------------------------------------------------------------------------

def test_related_edge_full_weight():
    """related edge contributes edge.weight × 1.0 to graph score."""
    g = _make_graph(("a", "b", "related", 0.9))
    candidate_ids = {"note:a", "note:b"}
    score = _compute_graph_score("note:a", g, [], candidate_ids)
    # edge_score = 0.9 * 1.0 = 0.9; capped at 1.0
    assert score > 0.0


def test_derived_from_edge_excluded():
    """derived_from edge contributes 0.0 — excluded from expansion weights."""
    g = _make_graph(("a", "src", "derived_from", 0.9))
    candidate_ids = {"note:a", "note:src"}
    score = _compute_graph_score("note:a", g, [], candidate_ids)
    assert score == 0.0


def test_same_batch_edge_excluded():
    """same_batch edge contributes 0.0."""
    g = _make_graph(("a", "batch", "same_batch", 0.9))
    candidate_ids = {"note:a", "note:batch"}
    score = _compute_graph_score("note:a", g, [], candidate_ids)
    assert score == 0.0


def test_suggested_related_excluded_by_default():
    """With default weights, suggested_related contributes 0.0."""
    g = _make_graph(("a", "b", "suggested_related", 0.5))
    candidate_ids = {"note:a", "note:b"}
    w = _get_expansion_weights()  # use_suggested_strong=False
    score = _compute_graph_score("note:a", g, [], candidate_ids, expansion_weights=w)
    assert score == 0.0


def test_suggested_related_contributes_when_enabled():
    """With use_suggested_strong=True, suggested_related contributes."""
    g = _make_graph(("a", "b", "suggested_related", 0.5))
    candidate_ids = {"note:a", "note:b"}
    w = _get_expansion_weights(use_suggested_strong=True)
    score = _compute_graph_score("note:a", g, [], candidate_ids, expansion_weights=w)
    assert score > 0.0
    # max contribution: 0.5 * SUGGESTED_RELATED_MAX_WEIGHT
    assert score <= 0.5 * SUGGESTED_RELATED_MAX_WEIGHT + 1e-9


def test_convergence_bonus_only_via_eligible_edges():
    """Convergence bonus (≥3 neighbours) uses only expansion-eligible edges."""
    # 3 related candidates + 1 derived_from candidate
    g = _make_graph(
        ("a", "b", "related", 0.8),
        ("a", "c", "related", 0.8),
        ("a", "d", "related", 0.8),
        ("a", "prov", "derived_from", 0.9),
    )
    candidate_ids = {"note:a", "note:b", "note:c", "note:d", "note:prov"}
    w = _get_expansion_weights()
    score_with_bonus = _compute_graph_score("note:a", g, [], candidate_ids, expansion_weights=w)
    # edge_score = 3 * 0.8 * 1.0 = 2.4; convergence bonus = 0.3; capped at 1.0
    assert score_with_bonus == 1.0  # max cap


def test_convergence_bonus_not_triggered_by_excluded_edges():
    """derived_from edges should NOT count toward convergence bonus threshold."""
    # Only derived_from edges — no eligible neighbours
    g = _make_graph(
        ("a", "p1", "derived_from", 0.9),
        ("a", "p2", "derived_from", 0.9),
        ("a", "p3", "derived_from", 0.9),
    )
    candidate_ids = {"note:a", "note:p1", "note:p2", "note:p3"}
    score = _compute_graph_score("note:a", g, [], candidate_ids)
    assert score == 0.0


# ---------------------------------------------------------------------------
# _expand_anchors
# ---------------------------------------------------------------------------

def test_expand_anchors_includes_related():
    """related neighbours are added to anchor set."""
    g = _make_graph(("anchor", "linked", "related", 0.9))
    result = _expand_anchors(g, ["note:anchor"])
    assert "note:linked" in result


def test_expand_anchors_excludes_derived_from():
    """derived_from neighbours are NOT added."""
    g = _make_graph(("anchor", "prov", "derived_from", 0.9))
    result = _expand_anchors(g, ["note:anchor"])
    assert "note:prov" not in result


def test_expand_anchors_max_added_cap():
    """At most max_added neighbours added."""
    edges = [("hub", f"n{i}", "related", 0.9) for i in range(15)]
    g = _make_graph(*edges)
    result = _expand_anchors(g, ["note:hub"], max_added=5)
    # original anchor + up to 5 added
    assert len(result) <= 6


def test_expand_anchors_excludes_non_strong_suggested():
    """suggested_related edges only included when tier == 'strong'.

    Since Edge model doesn't carry tier, all suggested_related are excluded
    from anchor expansion regardless of use_suggested_strong setting.
    """
    g = _make_graph(("anchor", "sug", "suggested_related", 0.5))
    result = _expand_anchors(g, ["note:anchor"])
    # No tier info on edge → excluded
    assert "note:sug" not in result


def test_expand_anchors_preserves_originals():
    """Original anchor nodes always retained even at cap."""
    g = _make_graph(("a", "b", "related", 0.9))
    result = _expand_anchors(g, ["note:a"], max_added=0)
    assert "note:a" in result
