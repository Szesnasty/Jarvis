"""Evaluation runner — runs queries against the retrieval pipeline and computes metrics."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


async def run_eval(
    workspace_path: Path,
    queries: list[dict],
    limit: int = 5,
) -> dict:
    """Run all queries against the current retrieval pipeline and compute metrics."""
    from services import retrieval

    results = []
    for q in queries:
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

        results.append({
            "query": q["query"],
            "type": q["type"],
            "recall": recall,
            "mrr": mrr,
            "precision": precision,
            "expected": list(expected),
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
        for t, rs in by_type.items()
    }

    return {
        "overall": {
            "avg_recall": avg_recall,
            "avg_mrr": avg_mrr,
            "avg_precision": avg_precision,
            "total": len(results),
        },
        "by_type": type_metrics,
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
