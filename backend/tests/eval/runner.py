"""Evaluation runner — runs queries against the retrieval pipeline and computes metrics."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _query_name(q: dict, idx: int) -> str:
    """Stable key for a query, suitable for JSON diffing across runs."""
    raw = q.get("query", f"query_{idx}")
    # Truncate at 60 chars, replace whitespace with underscores for readability
    return raw[:60].replace(" ", "_").replace("/", "-").lower()


def _token_budget_for(retrieved: list[dict], workspace_path: Path) -> int:
    """
    Estimate the approximate token budget consumed by the assembled prompt context
    for the given retrieved notes.  Uses the same ``len(text) // 4`` heuristic that
    ``context_builder.build_context`` applies internally so the value is consistent
    with what Claude actually receives.
    """
    total_chars = 0
    for item in retrieved:
        path = item.get("path", "")
        if not path:
            continue
        note_file = workspace_path / "memory" / path
        try:
            total_chars += len(note_file.read_text(encoding="utf-8"))
        except OSError:
            total_chars += item.get("word_count", 0) * 5  # rough fallback
    return total_chars // 4


async def run_eval(
    workspace_path: Path,
    queries: list[dict],
    limit: int = 5,
) -> dict:
    """Run all queries against the current retrieval pipeline and compute metrics.

    Returns a dict with keys:
      overall     — aggregate recall/mrr/precision across all queries
      by_type     — same metrics broken down by query ``type``
      per_query   — stable-key dict for baseline floor comparison (one entry per query)
      details     — full list of per-query result objects
    """
    from services import retrieval

    results = []
    for idx, q in enumerate(queries):
        try:
            retrieved = await retrieval.retrieve(
                q["query"], limit=limit, workspace_path=workspace_path,
            )
            retrieved_paths = [r["path"] for r in retrieved]
        except Exception as exc:
            logger.warning("Query failed: %s — %s", q["query"], exc)
            retrieved_paths = []
            retrieved = []

        expected = set(q["expected_paths"])
        found = set(retrieved_paths) & expected
        recall = len(found) / len(expected) if expected else 1.0

        # MRR: reciprocal rank of first expected result
        mrr = 0.0
        for i, path in enumerate(retrieved_paths):
            if path in expected:
                mrr = 1.0 / (i + 1)
                break

        # Precision@K
        precision = len(found) / len(retrieved_paths) if retrieved_paths else 0.0

        # Token budget estimate for the assembled prompt context
        token_budget = _token_budget_for(retrieved, workspace_path)

        results.append({
            "name": _query_name(q, idx),
            "query": q["query"],
            "type": q["type"],
            "recall": recall,
            "mrr": mrr,
            "precision": precision,
            "token_budget": token_budget,
            "expected": sorted(expected),
            "retrieved": retrieved_paths,
        })

    # Aggregate metrics
    avg_recall = sum(r["recall"] for r in results) / len(results) if results else 0
    avg_mrr = sum(r["mrr"] for r in results) / len(results) if results else 0
    avg_precision = sum(r["precision"] for r in results) / len(results) if results else 0

    by_type: dict[str, list] = {}
    for r in results:
        by_type.setdefault(r["type"], []).append(r)

    type_metrics = {
        t: {
            "avg_recall": sum(r["recall"] for r in rs) / len(rs),
            "avg_mrr": sum(r["mrr"] for r in rs) / len(rs),
            "avg_precision": sum(r["precision"] for r in rs) / len(rs),
            "count": len(rs),
        }
        for t, rs in sorted(by_type.items())  # stable key order
    }

    # Stable per-query dict for baseline comparison — sorted by name for git-diffable JSON
    per_query = {
        r["name"]: {
            "recall": r["recall"],
            "mrr": r["mrr"],
            "precision": r["precision"],
            "token_budget": r["token_budget"],
            "type": r["type"],
        }
        for r in sorted(results, key=lambda x: x["name"])
    }

    return {
        "overall": {
            "avg_recall": avg_recall,
            "avg_mrr": avg_mrr,
            "avg_precision": avg_precision,
            "total": len(results),
        },
        "by_type": type_metrics,
        "per_query": per_query,
        "details": results,
    }


async def eval_graph_anchors(
    queries: list[dict],
    workspace_path: Path,
) -> dict:
    """Measure how well anchor extraction matches expected anchors."""
    from services import graph_service, retrieval

    graph = graph_service.load_graph(workspace_path)
    if not graph:
        return {"error": "no graph", "anchor_recall": 0, "total_expected": 0}

    hits = 0
    total = 0
    for q in queries:
        if not q.get("expected_anchors"):
            continue
        try:
            actual = await retrieval._extract_query_anchors(q["query"], graph, workspace_path)
        except Exception:
            actual = []
        expected = set(q["expected_anchors"])
        total += len(expected)
        hits += len(set(actual) & expected)

    return {
        "anchor_recall": hits / total if total else 0,
        "total_expected": total,
        "total_hits": hits,
    }


def save_snapshot(results: dict, step_name: str, output_dir: Path) -> Path:
    """Save evaluation results as a JSON snapshot."""
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "step": step_name,
        "timestamp": datetime.now().isoformat(),
        **results,
    }
    path = output_dir / f"{step_name}.json"
    path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    logger.info("Saved eval snapshot: %s", path)
    return path
