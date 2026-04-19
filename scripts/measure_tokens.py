#!/usr/bin/env python3
"""
Token cost comparison: with Jarvis MCP vs without.

Usage:
  python3 scripts/measure_tokens.py --query "sprint 23"
  python3 scripts/measure_tokens.py --query "sprint 23" --scope jira
"""

import argparse
import json
import math
import os
import re
from pathlib import Path

WORKSPACE = Path.home() / "Jarvis"
MCP_LOG = WORKSPACE / "app" / "logs" / "mcp.jsonl"
TOKEN_LOG = WORKSPACE / "app" / "logs" / "token_usage.jsonl"

# Rough token cost (Claude Sonnet 4, April 2026)
INPUT_COST_PER_1M = 3.0   # USD per 1M input tokens
OUTPUT_COST_PER_1M = 15.0  # USD per 1M output tokens


def chars_to_tokens(chars: int) -> int:
    """Rough estimate: 1 token ≈ 4 chars (English), 3 chars (Polish/mixed)."""
    return math.ceil(chars / 3.5)


def find_matching_files(query: str, scope: str) -> list[Path]:
    """Find memory files that match the query terms."""
    terms = [t.lower() for t in query.split()]
    root = WORKSPACE / "memory"
    if scope == "jira":
        root = root / "jira"
    elif scope == "notes":
        root = root / "notes"

    matched = []
    for f in root.rglob("*.md"):
        content = f.read_text(errors="ignore").lower()
        if any(term in content for term in terms):
            matched.append(f)
    return matched


def raw_baseline(query: str, scope: str) -> dict:
    """Estimate tokens if user pastes all matching files without Jarvis."""
    files = find_matching_files(query, scope)
    total_chars = sum(f.stat().st_size for f in files)
    total_tokens = chars_to_tokens(total_chars)
    return {
        "files_matched": len(files),
        "raw_chars": total_chars,
        "estimated_tokens": total_tokens,
        "estimated_cost_usd": round(total_tokens / 1_000_000 * INPUT_COST_PER_1M, 4),
    }


def jarvis_context(query: str, limit: int = 20) -> dict:
    """Read last N MCP tool calls as proxy for context returned by Jarvis."""
    if not MCP_LOG.exists():
        return {"error": "mcp.jsonl not found"}

    lines = MCP_LOG.read_text().strip().splitlines()
    recent = [json.loads(l) for l in lines[-limit:]]

    # Filter tools that likely ran for this query (last session = last burst of calls)
    # Use all entries as proxy for one Cursor session
    total_output_tokens = sum(e.get("output_tokens", 0) for e in recent)
    tools_used = [e["tool"] for e in recent]
    return {
        "tool_calls": len(recent),
        "tools_used": tools_used,
        "context_tokens_returned": total_output_tokens,
        "estimated_cost_usd": round(total_output_tokens / 1_000_000 * INPUT_COST_PER_1M, 4),
        "note": "output_tokens here = tokens in MCP response payload fed as context to your LLM",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="sprint 23", help="Search query")
    parser.add_argument("--scope", default="all", choices=["all", "jira", "notes"])
    args = parser.parse_args()

    baseline = raw_baseline(args.query, args.scope)
    with_jarvis = jarvis_context(args.query)

    savings_tokens = baseline["estimated_tokens"] - with_jarvis.get("context_tokens_returned", 0)
    savings_pct = round(savings_tokens / max(baseline["estimated_tokens"], 1) * 100, 1)
    savings_usd = round(baseline["estimated_cost_usd"] - with_jarvis.get("estimated_cost_usd", 0), 4)

    print(f"\n{'='*60}")
    print(f"  TOKEN COST COMPARISON — query: '{args.query}'")
    print(f"{'='*60}")
    print(f"\n  WITHOUT Jarvis (paste all matching raw files):")
    print(f"    Files matched:      {baseline['files_matched']}")
    print(f"    Raw chars:          {baseline['raw_chars']:,}")
    print(f"    Estimated tokens:   {baseline['estimated_tokens']:,}")
    print(f"    Input cost:         ${baseline['estimated_cost_usd']:.4f}")

    print(f"\n  WITH Jarvis MCP (compressed, retrieved context):")
    print(f"    Tool calls:         {with_jarvis.get('tool_calls', 'N/A')}")
    print(f"    Context tokens:     {with_jarvis.get('context_tokens_returned', 'N/A'):,}")
    print(f"    Input cost:         ${with_jarvis.get('estimated_cost_usd', 0):.4f}")

    print(f"\n  SAVINGS:")
    print(f"    Tokens saved:       {savings_tokens:,}  ({savings_pct}% reduction)")
    print(f"    Cost saved:         ${savings_usd:.4f}")
    print(f"{'='*60}\n")
    print("  Note: Cost model = Claude Sonnet 4 @ $3/1M input tokens.")
    print("  MCP context = last 20 tool call responses in mcp.jsonl.")
    print("  For a cleaner benchmark: clear mcp.jsonl, run one query in Cursor,")
    print("  then run this script.\n")


if __name__ == "__main__":
    main()
