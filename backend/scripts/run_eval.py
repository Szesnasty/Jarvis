#!/usr/bin/env python3
"""Step 28c — CLI diff runner for retrieval evaluation.

Runs all 30 reference queries against a workspace, then optionally compares to a
committed baseline JSON and prints a diff table.

Usage
-----
  # Run against a workspace built from the fixture Markdowns:
  python backend/scripts/run_eval.py

  # Run against a custom workspace:
  python backend/scripts/run_eval.py --workspace ~/Jarvis-eval

  # Compare to a specific baseline:
  python backend/scripts/run_eval.py --baseline backend/tests/eval/baselines/step-28c.json

  # Save the output (e.g. to freeze as the new baseline):
  python backend/scripts/run_eval.py --output /tmp/step-28c.json

  # Run without building the workspace (assumes it already exists):
  python backend/scripts/run_eval.py --no-setup --workspace /tmp/jarvis-eval
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

# Resolve backend root so the script works regardless of cwd
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

HERE = _BACKEND / "tests" / "eval"
DEFAULT_WORKSPACE = Path("/tmp/jarvis-eval")
DEFAULT_BASELINE = HERE / "baselines" / "step-28c.json"
FIXTURE_WS = HERE / "fixtures" / "reference_workspace"


# ─── Workspace setup ────────────────────────────────────────────────────────

async def _setup_workspace(workspace: Path) -> None:
    from models.database import init_database
    from services.memory_service import index_note_file

    fixture_memory = FIXTURE_WS / "memory"
    if not fixture_memory.exists():
        print(
            f"ERROR: Reference workspace fixture not found at {fixture_memory}.\n"
            "Ensure backend/tests/eval/fixtures/reference_workspace/ is present.",
            file=sys.stderr,
        )
        sys.exit(1)

    memory = workspace / "memory"
    app = workspace / "app"
    graph_dir = workspace / "graph"

    for d in (memory, app, graph_dir):
        d.mkdir(parents=True, exist_ok=True)

    shutil.copytree(fixture_memory, memory, dirs_exist_ok=True)
    await init_database(app / "jarvis.db")

    md_files = sorted(memory.rglob("*.md"))
    for md_path in md_files:
        rel = md_path.relative_to(memory).as_posix()
        try:
            await index_note_file(rel, workspace_path=workspace)
        except Exception as exc:
            print(f"  WARNING: {rel}: {exc}", file=sys.stderr)
    print(f"Workspace ready ({len(md_files)} notes indexed): {workspace}")


# ─── Diff table ─────────────────────────────────────────────────────────────

def _print_diff_table(current: dict, baseline: dict | None) -> None:
    has_baseline = baseline is not None
    col_w = 50

    def _sym(diff: float) -> str:
        if diff > 0.01:
            return "✓"
        if diff < -0.01:
            return "⚠"
        return " "

    header = f"{'Query':{col_w}}  {'Recall':>6}  {'ΔMRR':>8}" if has_baseline else f"{'Query':{col_w}}  {'Recall':>6}  {'MRR':>6}"
    print("\n" + header)
    print("─" * len(header))

    details = sorted(current["details"], key=lambda r: r.get("name", r["query"]))
    for r in details:
        q_short = r["query"][:col_w]
        if has_baseline:
            bq: dict = baseline.get("per_query", {}).get(r.get("name", ""), {})
            d_recall = r["recall"] - bq.get("recall", r["recall"])
            d_mrr = r["mrr"] - bq.get("mrr", r["mrr"])
            sym = _sym(d_recall)
            print(f"{q_short:{col_w}}  {r['recall']:>6.2f}  {d_recall:>+7.2f}{sym}  {r['mrr']:>5.2f}  {d_mrr:>+6.2f}")
        else:
            print(f"{q_short:{col_w}}  {r['recall']:>6.2f}  {r['mrr']:>6.2f}")

    print("─" * len(header))

    # By-type summary
    print("\nBy type:")
    for qtype, metrics in sorted(current["by_type"].items()):
        line = f"  {qtype:<18}  recall={metrics['avg_recall']:.3f}  mrr={metrics['avg_mrr']:.3f}  n={metrics['count']}"
        if has_baseline:
            b_type = baseline.get("by_type", {}).get(qtype, {})
            diff = metrics["avg_recall"] - b_type.get("avg_recall", metrics["avg_recall"])
            sym = _sym(diff)
            line += f"  Δrecall={diff:+.3f}{sym}"
        print(line)

    # Overall
    ov = current["overall"]
    print(f"\nOverall  recall={ov['avg_recall']:.4f}  mrr={ov['avg_mrr']:.4f}  total={ov['total']}")
    if has_baseline:
        b_recall = baseline.get("overall", {}).get("avg_recall", ov["avg_recall"])
        d = ov["avg_recall"] - b_recall
        sym = _sym(d)
        print(f"         Δrecall={d:+.4f}{sym}")


# ─── Main ───────────────────────────────────────────────────────────────────

async def _main(args: argparse.Namespace) -> None:
    from tests.eval.queries_reference import REFERENCE_QUERIES
    from tests.eval.runner import run_eval

    # Disable embeddings in eval unless explicitly enabled (faster, less noise)
    if not os.environ.get("JARVIS_ALLOW_EMBEDDINGS"):
        os.environ.setdefault("JARVIS_DISABLE_EMBEDDINGS", "1")

    workspace = args.workspace
    if not args.no_setup:
        print(f"Building workspace from fixture Markdowns → {workspace}")
        await _setup_workspace(workspace)
    else:
        if not (workspace / "memory").exists():
            print(f"ERROR: Workspace not found at {workspace}. Remove --no-setup or run setup.", file=sys.stderr)
            sys.exit(1)

    print(f"\nRunning {len(REFERENCE_QUERIES)} queries (limit={args.limit})…")
    results = await run_eval(workspace, REFERENCE_QUERIES, limit=args.limit)

    baseline = None
    if args.baseline and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        print(f"Comparing to baseline: {args.baseline}")
    elif args.baseline:
        print(f"Baseline not found ({args.baseline}) — showing raw results only.")

    _print_diff_table(results, baseline)

    if args.output:
        snapshot = {
            "step": "step-28c",
            **results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved: {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval eval against reference PDFs")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE,
                        help=f"Workspace path (default: {DEFAULT_WORKSPACE})")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE,
                        help=f"Baseline JSON for comparison (default: {DEFAULT_BASELINE})")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write run results to this JSON file")
    parser.add_argument("--limit", type=int, default=5,
                        help="Recall@K limit (default: 5)")
    parser.add_argument("--no-setup", action="store_true",
                        help="Skip workspace setup (assumes workspace already exists)")
    args = parser.parse_args()

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
