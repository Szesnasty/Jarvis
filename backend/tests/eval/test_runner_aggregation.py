"""Unit tests for the eval runner aggregation logic — Step 28c.

Covers:
  1. Per-bucket aggregation correctness.
  2. Empty bucket (no queries of that type) does not crash.
  3. Baseline diff output has stable (sorted) key order.
  4. _query_name generates stable keys suitable for JSON diffing.
  5. per_query dict is present in run_eval output.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.eval.runner import _query_name, run_eval


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_query(q: str, qtype: str, expected: list[str]) -> dict:
    return {
        "query": q,
        "type": qtype,
        "expected_paths": expected,
        "min_recall": 0.5,
    }


# ─── _query_name ────────────────────────────────────────────────────────────

class TestQueryName:
    def test_spaces_replaced_with_underscores(self):
        name = _query_name({"query": "hello world"}, 0)
        assert " " not in name
        assert "_" in name

    def test_slashes_replaced_with_dash(self):
        name = _query_name({"query": "NIST/OWASP overlap"}, 0)
        assert "/" not in name

    def test_truncated_at_60_chars(self):
        long_query = "a" * 80
        name = _query_name({"query": long_query}, 0)
        assert len(name) == 60

    def test_fallback_for_missing_query(self):
        name = _query_name({}, 7)
        assert name == "query_7"

    def test_lowercased(self):
        name = _query_name({"query": "UPPER CASE QUERY"}, 0)
        assert name == name.lower()


# ─── run_eval aggregation ────────────────────────────────────────────────────

SYNTHETIC_QUERIES = [
    _make_query("factual q1", "factual", ["a/b.md"]),
    _make_query("factual q2", "factual", ["c/d.md"]),
    _make_query("cross doc q1", "cross_doc", ["a/b.md", "e/f.md"]),
    _make_query("section typed q1", "section_typed", ["g/h.md"]),
]


def _mock_retrieval(retrieved_map: dict):
    """Create a patched retrieval.retrieve that returns pre-canned results."""
    async def _retrieve(query: str, limit: int, workspace_path: Path):
        return [{"path": p} for p in retrieved_map.get(query, [])]
    return _retrieve


@pytest.mark.anyio
async def test_per_bucket_aggregation_correct(tmp_path):
    """Recall, MRR, precision values aggregate correctly per query type."""
    # factual q1: retrieved = ["a/b.md"]  → recall 1.0, mrr 1.0, precision 1.0
    # factual q2: retrieved = []          → recall 0.0, mrr 0.0, precision 0.0
    # cross_doc:  retrieved = ["a/b.md"]  → recall 0.5, mrr 1.0, precision 1.0
    # section:    retrieved = ["g/h.md"]  → recall 1.0, mrr 1.0, precision 1.0
    retrieved_map = {
        "factual q1": ["a/b.md"],
        "factual q2": [],
        "cross doc q1": ["a/b.md"],
        "section typed q1": ["g/h.md"],
    }

    with patch("services.retrieval.retrieve", side_effect=_mock_retrieval(retrieved_map)):
        results = await run_eval(tmp_path, SYNTHETIC_QUERIES)

    by_type = results["by_type"]

    # factual: avg_recall = (1.0 + 0.0) / 2 = 0.5
    assert abs(by_type["factual"]["avg_recall"] - 0.5) < 1e-9
    # cross_doc: recall = 1/2 = 0.5; mrr = 1.0/1 = 1.0
    assert abs(by_type["cross_doc"]["avg_recall"] - 0.5) < 1e-9
    assert abs(by_type["cross_doc"]["avg_mrr"] - 1.0) < 1e-9
    # section_typed: recall = 1.0
    assert abs(by_type["section_typed"]["avg_recall"] - 1.0) < 1e-9


@pytest.mark.anyio
async def test_empty_bucket_does_not_crash(tmp_path):
    """A query type present in the data produces a bucket; absent types are simply absent."""
    queries = [_make_query("only factual q", "factual", ["x/y.md"])]

    with patch("services.retrieval.retrieve", side_effect=_mock_retrieval({"only factual q": ["x/y.md"]})):
        results = await run_eval(tmp_path, queries)

    # Should have factual bucket, no crash from other types being absent
    assert "factual" in results["by_type"]
    assert "cross_doc" not in results["by_type"]
    assert "polish" not in results["by_type"]


@pytest.mark.anyio
async def test_per_query_dict_stable_key_order(tmp_path):
    """per_query keys are sorted alphabetically for git-diffable JSON output."""
    with patch("services.retrieval.retrieve", side_effect=_mock_retrieval({})):
        results = await run_eval(tmp_path, SYNTHETIC_QUERIES)

    keys = list(results["per_query"].keys())
    assert keys == sorted(keys), f"per_query keys not sorted: {keys}"


@pytest.mark.anyio
async def test_per_query_contains_required_fields(tmp_path):
    """Each per_query entry has recall, mrr, precision, token_budget, type."""
    with patch("services.retrieval.retrieve", side_effect=_mock_retrieval({})):
        results = await run_eval(tmp_path, SYNTHETIC_QUERIES)

    for name, entry in results["per_query"].items():
        assert "recall" in entry, f"missing recall in {name}"
        assert "mrr" in entry, f"missing mrr in {name}"
        assert "precision" in entry, f"missing precision in {name}"
        assert "token_budget" in entry, f"missing token_budget in {name}"
        assert "type" in entry, f"missing type in {name}"


@pytest.mark.anyio
async def test_by_type_keys_stable(tmp_path):
    """by_type keys should be sorted so JSON diffs are clean."""
    with patch("services.retrieval.retrieve", side_effect=_mock_retrieval({})):
        results = await run_eval(tmp_path, SYNTHETIC_QUERIES)

    keys = list(results["by_type"].keys())
    assert keys == sorted(keys), f"by_type keys not sorted: {keys}"
