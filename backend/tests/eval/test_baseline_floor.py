"""Step 28c — No-regression gate against the committed baseline.

This test is opt-in behind the ``JARVIS_EVAL_FLOOR=1`` environment variable.
It will also skip automatically if:
  - The baseline JSON does not exist yet.
  - The reference workspace fixture is absent.
  - The JARVIS_DISABLE_EVAL env var is set.

Run it before merging any change that touches retrieval, indexing, or context building:

    JARVIS_EVAL_FLOOR=1 pytest backend/tests/eval/test_baseline_floor.py -v

A failure means that at least one query's recall dropped more than 5% below the
baseline, or that the overall mean Recall@5 dropped at all.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
BASELINE_PATH = HERE / "baselines" / "step-28c.json"
FIXTURE_WS = HERE / "fixtures" / "reference_workspace"

# Skip unless opt-in
_EVAL_ENABLED = os.environ.get("JARVIS_EVAL_FLOOR") == "1"
_EVAL_DISABLED_EXPLICITLY = os.environ.get("JARVIS_DISABLE_EVAL") == "1"

pytestmark = pytest.mark.anyio


def _skip_unless_enabled():
    if _EVAL_DISABLED_EXPLICITLY:
        pytest.skip("JARVIS_DISABLE_EVAL=1 — eval skipped")
    if not _EVAL_ENABLED:
        pytest.skip(
            "Set JARVIS_EVAL_FLOOR=1 to run the no-regression eval gate. "
            "This requires a pre-built reference workspace."
        )
    if not BASELINE_PATH.exists():
        pytest.skip(
            f"Baseline not found: {BASELINE_PATH}\n"
            "Run 'python backend/scripts/run_eval.py' to generate it first."
        )
    if not (FIXTURE_WS / "memory").exists():
        pytest.skip(
            f"Reference workspace fixture missing: {FIXTURE_WS / 'memory'}\n"
            "Ensure backend/tests/eval/fixtures/reference_workspace/ is checked in."
        )


@pytest.fixture(scope="module")
async def eval_results(tmp_path_factory):
    """Build a fresh workspace from the fixture Markdowns and run the full eval."""
    _skip_unless_enabled()

    # Import inside fixture so normal test runs don't trigger heavy imports
    from models.database import init_database
    from services.memory_service import index_note_file
    from tests.eval.queries_reference import REFERENCE_QUERIES
    from tests.eval.runner import run_eval

    workspace = tmp_path_factory.mktemp("jarvis-eval")
    memory = workspace / "memory"
    app = workspace / "app"
    (workspace / "graph").mkdir(parents=True)
    app.mkdir(parents=True)

    shutil.copytree(FIXTURE_WS / "memory", memory, dirs_exist_ok=True)
    await init_database(app / "jarvis.db")

    for md_path in sorted(memory.rglob("*.md")):
        rel = md_path.relative_to(memory).as_posix()
        try:
            await index_note_file(rel, workspace_path=workspace)
        except Exception as exc:
            print(f"WARNING: could not index {rel}: {exc}", file=sys.stderr)

    return await run_eval(workspace, REFERENCE_QUERIES, limit=5)


@pytest.mark.anyio
async def test_no_recall_regression_per_query(eval_results):
    """Per-query recall must not drop more than 5% below baseline."""
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_pq = baseline["per_query"]
    current_pq = eval_results["per_query"]

    failures = []
    for name, prev in baseline_pq.items():
        cur = current_pq.get(name)
        if cur is None:
            failures.append(f"{name}: query not found in current run")
            continue
        diff = cur["recall"] - prev["recall"]
        if diff < -0.05:
            failures.append(
                f"{name}: recall {cur['recall']:.3f} vs baseline {prev['recall']:.3f} "
                f"(Δ {diff:+.3f})"
            )

    assert not failures, "Recall regression(s) detected:\n" + "\n".join(failures)


@pytest.mark.anyio
async def test_no_overall_recall_regression(eval_results):
    """Overall mean Recall@5 must not drop at all (zero tolerance)."""
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    prev_recall = baseline["overall"]["avg_recall"]
    cur_recall = eval_results["overall"]["avg_recall"]
    assert cur_recall >= prev_recall, (
        f"Overall Recall@5 dropped: {cur_recall:.4f} < baseline {prev_recall:.4f}"
    )


@pytest.mark.anyio
async def test_mean_recall_above_floor(eval_results):
    """Mean Recall@5 across all 30 queries must be ≥ 0.55 (baseline floor)."""
    cur_recall = eval_results["overall"]["avg_recall"]
    assert cur_recall >= 0.55, (
        f"Mean Recall@5 {cur_recall:.4f} is below the 0.55 floor set in Step 28c."
    )
