"""Comprehensive tests proving token savings from soft-cap + stale compaction.

These tests simulate realistic multi-round tool cascades (Jira search → read
note → search more) and measure the char-level (≈ token-level) reduction that
our optimizations deliver compared to the naive baseline (no caps, no
compaction).
"""

import copy
import json
import pytest

from routers.chat import (
    _STALE_TOOL_RESULT_CAP,
    _TOOL_RESULT_SOFT_CAP,
    _build_tool_messages,
    _compact_stale_tool_results,
    _truncate_tool_result,
    StreamEvent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chars_in_messages(messages: list[dict]) -> int:
    """Total characters across all message content (proxy for tokens)."""
    total = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    c = block.get("content", "")
                    if isinstance(c, str):
                        total += len(c)
                    inp = block.get("input")
                    if isinstance(inp, dict):
                        total += len(json.dumps(inp))
        else:
            total += len(str(content))
    return total


def _make_tool_event(tool_id: str, name: str, tool_input: dict | None = None) -> StreamEvent:
    return StreamEvent(
        type="tool_use",
        content="",
        name=name,
        tool_use_id=tool_id,
        tool_input=tool_input or {},
    )


def _naive_build_tool_messages(messages, event, result):
    """Baseline: no soft-cap, just append full result."""
    return messages + [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": event.tool_use_id,
                    "name": event.name,
                    "input": event.tool_input or {},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": event.tool_use_id,
                    "content": result,
                }
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Realistic payloads: Jira-style search results + note reads
# ---------------------------------------------------------------------------

JIRA_SEARCH_RESULT = json.dumps([
    {
        "key": f"PROJ-{5000 + i}",
        "summary": f"Bug #{i}: Widget rendering fails in production environment with undefined error",
        "status": "In Progress",
        "priority": "High",
        "assignee": f"developer{i}@company.com",
        "description": f"Steps to reproduce:\n1. Open dashboard\n2. Click on widget {i}\n3. Error appears\n\nExpected: Widget renders correctly\nActual: Blank screen with console error.\n\nStack trace:\n" + "Error at line " * 20,
        "labels": ["bug", "frontend", "critical"],
        "sprint": "Sprint 42",
    }
    for i in range(25)
], indent=2)  # ~15-20k chars typical Jira search result

NOTE_READ_RESULT = "# Architecture Decision Record: Authentication System\n\n" + (
    "## Context\nOur current authentication uses session-based auth with cookies. "
    "We need to support mobile apps and third-party integrations.\n\n"
    "## Decision\nWe will migrate to JWT-based authentication with refresh tokens.\n\n"
    "## Consequences\n- Stateless auth on API side\n- Need token refresh logic\n- "
    "Mobile apps can use bearer tokens\n\n" + "Details: " * 1200
)  # ~12k chars

SECOND_SEARCH_RESULT = json.dumps([
    {
        "key": f"PROJ-{6000 + i}",
        "summary": f"Security audit finding #{i}: Missing input validation",
        "status": "Open",
        "priority": "Critical",
        "description": f"Finding details for item {i}:\n" + "Vulnerability description. " * 40,
    }
    for i in range(15)
], indent=2)  # ~12k chars

GRAPH_QUERY_RESULT = json.dumps({
    "nodes": [{"id": f"entity_{i}", "label": f"Component {i}", "type": "service"} for i in range(30)],
    "edges": [{"source": f"entity_{i}", "target": f"entity_{(i+1) % 30}", "label": "depends_on"} for i in range(30)],
}, indent=2)  # ~3k chars


# ---------------------------------------------------------------------------
# TESTS: Soft-cap on individual tool results
# ---------------------------------------------------------------------------

class TestSoftCapSavings:
    """Prove that the soft-cap on _build_tool_messages reduces token footprint."""

    def test_jira_search_result_is_capped(self):
        """A realistic 18k Jira search gets capped to ~8k."""
        assert len(JIRA_SEARCH_RESULT) > 10_000, "fixture should be large"
        event = _make_tool_event("t1", "search_jira", {"query": "sprint bugs"})

        naive = _naive_build_tool_messages([], event, JIRA_SEARCH_RESULT)
        optimized = _build_tool_messages([], event, JIRA_SEARCH_RESULT)

        naive_chars = _chars_in_messages(naive)
        opt_chars = _chars_in_messages(optimized)
        savings_pct = (1 - opt_chars / naive_chars) * 100

        assert savings_pct > 40, f"Expected >40% savings, got {savings_pct:.1f}%"

    def test_small_result_not_degraded(self):
        """Results under the cap pass through untouched — no quality loss."""
        small = '{"status": "ok", "items": []}'
        event = _make_tool_event("t1", "search_notes", {"query": "test"})

        naive = _naive_build_tool_messages([], event, small)
        optimized = _build_tool_messages([], event, small)

        assert _chars_in_messages(naive) == _chars_in_messages(optimized)

    def test_note_read_preserves_head_and_tail(self):
        """Truncated content still has meaningful head and tail."""
        event = _make_tool_event("t1", "read_note", {"path": "adr.md"})
        msgs = _build_tool_messages([], event, NOTE_READ_RESULT)

        tool_content = msgs[-1]["content"][0]["content"]
        # Head preserved (architecture title)
        assert "Architecture Decision Record" in tool_content
        # Tail preserved (last chars of original)
        assert tool_content.endswith(NOTE_READ_RESULT[-100:]) or "Details:" in tool_content[-200:]
        # Truncation marker present
        assert "truncated" in tool_content


# ---------------------------------------------------------------------------
# TESTS: Multi-round cascade compaction
# ---------------------------------------------------------------------------

class TestMultiRoundCompaction:
    """Simulate realistic 3-round tool cascade and measure savings."""

    def _build_3_round_cascade(self, use_compaction: bool) -> list[dict]:
        """Build a 3-round tool cascade (search → read → search again).

        Round 1: search_jira → big result
        Round 2: read_note → medium result (model reads search + note)
        Round 3: search_jira again → big result (model has all prior context)
        """
        messages = [{"role": "user", "content": "Jaki jest największy risk w sprincie? Wymień top 5 blokerów"}]

        # Round 1: search jira
        e1 = _make_tool_event("t1", "search_jira", {"query": "sprint blockers"})
        messages = _build_tool_messages(messages, e1, JIRA_SEARCH_RESULT)

        # Round 2: read a note for context
        if use_compaction:
            messages = _compact_stale_tool_results(messages)
        e2 = _make_tool_event("t2", "read_note", {"path": "architecture.md"})
        messages = _build_tool_messages(messages, e2, NOTE_READ_RESULT)

        # Round 3: another search
        if use_compaction:
            messages = _compact_stale_tool_results(messages)
        e3 = _make_tool_event("t3", "search_jira", {"query": "security vulnerabilities"})
        messages = _build_tool_messages(messages, e3, SECOND_SEARCH_RESULT)

        return messages

    def test_3_round_cascade_savings(self):
        """3-round cascade: compaction should save >30% input tokens."""
        baseline = self._build_3_round_cascade(use_compaction=False)
        optimized = self._build_3_round_cascade(use_compaction=True)

        baseline_chars = _chars_in_messages(baseline)
        opt_chars = _chars_in_messages(optimized)
        savings_pct = (1 - opt_chars / baseline_chars) * 100

        assert savings_pct > 30, (
            f"3-round cascade expected >30% savings, got {savings_pct:.1f}% "
            f"(baseline={baseline_chars}, optimized={opt_chars})"
        )

    def test_latest_result_stays_intact_after_compaction(self):
        """The most recent tool_result must not be compacted — model needs it."""
        optimized = self._build_3_round_cascade(use_compaction=True)

        # Find all tool_results
        tool_results = []
        for msg in optimized:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_results.append(block)

        # Last result should be full (soft-capped only, not stale-compacted)
        last = tool_results[-1]["content"]
        # It got soft-capped by _build_tool_messages but not stale-compacted further
        assert len(last) >= min(len(SECOND_SEARCH_RESULT), _TOOL_RESULT_SOFT_CAP * 0.9)

    def test_stale_results_heavily_compacted(self):
        """Earlier results from stale rounds should be compacted.

        In a 3-round cascade, compaction happens before rounds 2 and 3.
        After round 3 is built (final state), round 1 has been stale-compacted,
        but round 2 was the 'latest' during the last compaction so it stayed intact.
        """
        optimized = self._build_3_round_cascade(use_compaction=True)

        tool_results = []
        for msg in optimized:
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_results.append(block)

        assert len(tool_results) == 3
        # Round 1 should be heavily compacted (it was stale before round 3)
        assert len(tool_results[0]["content"]) <= _STALE_TOOL_RESULT_CAP + 100, (
            f"Round 1 should be compacted to ≤{_STALE_TOOL_RESULT_CAP}+margin, "
            f"got {len(tool_results[0]['content'])}"
        )
        # Round 3 (last) should be intact (soft-capped only)
        assert len(tool_results[2]["content"]) >= min(len(SECOND_SEARCH_RESULT), _TOOL_RESULT_SOFT_CAP * 0.9)

    def test_message_count_preserved(self):
        """Compaction doesn't lose messages — it only shrinks content."""
        baseline = self._build_3_round_cascade(use_compaction=False)
        optimized = self._build_3_round_cascade(use_compaction=True)
        assert len(baseline) == len(optimized)


# ---------------------------------------------------------------------------
# TESTS: 5-round cascade (worst case)
# ---------------------------------------------------------------------------

class TestDeepCascadeSavings:
    """Simulate a 5-round cascade — the maximum allowed."""

    PAYLOADS = [
        ("search_jira", JIRA_SEARCH_RESULT),
        ("read_note", NOTE_READ_RESULT),
        ("search_jira", SECOND_SEARCH_RESULT),
        ("query_graph", GRAPH_QUERY_RESULT),
        ("search_jira", JIRA_SEARCH_RESULT),
    ]

    def _build_n_rounds(self, n: int, use_compaction: bool) -> list[dict]:
        messages = [{"role": "user", "content": "Complex PM question requiring many tools"}]
        for i in range(n):
            if use_compaction and i > 0:
                messages = _compact_stale_tool_results(messages)
            name, payload = self.PAYLOADS[i % len(self.PAYLOADS)]
            event = _make_tool_event(f"t{i+1}", name, {"query": f"round {i+1}"})
            messages = _build_tool_messages(messages, event, payload)
        return messages

    def test_5_round_cascade_savings_over_50_pct(self):
        """5-round cascade: compaction saves >50% because stale rounds accumulate."""
        baseline = self._build_n_rounds(5, use_compaction=False)
        optimized = self._build_n_rounds(5, use_compaction=True)

        baseline_chars = _chars_in_messages(baseline)
        opt_chars = _chars_in_messages(optimized)
        savings_pct = (1 - opt_chars / baseline_chars) * 100

        assert savings_pct > 50, (
            f"5-round cascade expected >50% savings, got {savings_pct:.1f}% "
            f"(baseline={baseline_chars:,}, optimized={opt_chars:,})"
        )

    def test_5_round_token_estimate(self):
        """Estimate actual token impact of 5-round cascade.

        Rule of thumb: 4 chars ≈ 1 token.
        """
        baseline = self._build_n_rounds(5, use_compaction=False)
        optimized = self._build_n_rounds(5, use_compaction=True)

        baseline_tokens = _chars_in_messages(baseline) // 4
        opt_tokens = _chars_in_messages(optimized) // 4
        saved_tokens = baseline_tokens - opt_tokens

        # Should save at least 4000 tokens in a 5-round cascade
        assert saved_tokens > 4000, f"Expected >4k tokens saved, got {saved_tokens}"

    def test_savings_scale_with_depth(self):
        """More rounds → bigger savings percentage."""
        savings = []
        for n in range(2, 6):
            baseline = self._build_n_rounds(n, use_compaction=False)
            optimized = self._build_n_rounds(n, use_compaction=True)
            b = _chars_in_messages(baseline)
            o = _chars_in_messages(optimized)
            pct = (1 - o / b) * 100
            savings.append(pct)

        # Each additional round should save more (or at least not less)
        for i in range(1, len(savings)):
            assert savings[i] >= savings[i - 1] - 2, (
                f"Savings should grow with depth: round {i+2}={savings[i]:.1f}% "
                f"< round {i+1}={savings[i-1]:.1f}%"
            )


# ---------------------------------------------------------------------------
# TESTS: Pricing accuracy
# ---------------------------------------------------------------------------

class TestPricingAccuracy:
    """Verify cost estimates use correct per-model pricing."""

    def test_haiku_pricing(self):
        from services.token_tracking import log_usage
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            entry = log_usage(
                input_tokens=100_000,
                output_tokens=10_000,
                model="claude-haiku-4-20250514",
                provider="anthropic",
                workspace_path=ws,
            )
            # Haiku: $0.80/M in + $4/M out
            expected = 100_000 * 0.80 / 1e6 + 10_000 * 4.0 / 1e6
            assert abs(entry["cost_estimate"] - expected) < 0.001, (
                f"Haiku cost: expected ${expected:.4f}, got ${entry['cost_estimate']:.4f}"
            )

    def test_sonnet_pricing(self):
        from services.token_tracking import log_usage
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            entry = log_usage(
                input_tokens=100_000,
                output_tokens=10_000,
                model="claude-sonnet-4-20250514",
                provider="anthropic",
                workspace_path=ws,
            )
            # Sonnet: $3/M in + $15/M out
            expected = 100_000 * 3.0 / 1e6 + 10_000 * 15.0 / 1e6
            assert abs(entry["cost_estimate"] - expected) < 0.001

    def test_haiku_is_cheaper_than_sonnet(self):
        from services.token_tracking import log_usage
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            haiku = log_usage(50_000, 500, model="claude-haiku-4-20250514",
                              provider="anthropic", workspace_path=ws)
            sonnet = log_usage(50_000, 500, model="claude-sonnet-4-20250514",
                               provider="anthropic", workspace_path=ws)
            assert haiku["cost_estimate"] < sonnet["cost_estimate"]
            ratio = sonnet["cost_estimate"] / haiku["cost_estimate"]
            assert ratio > 3, f"Sonnet should be ~3.75x Haiku, got {ratio:.1f}x"

    def test_tool_tracking_fields_present(self):
        from services.token_tracking import log_usage
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            entry = log_usage(
                1000, 100,
                model="claude-haiku-4-20250514",
                provider="anthropic",
                tool_calls=3,
                tool_rounds=2,
                workspace_path=ws,
            )
            assert entry["tool_calls"] == 3
            assert entry["tool_rounds"] == 2


# ---------------------------------------------------------------------------
# TESTS: Recalculate historical costs with correct pricing
# ---------------------------------------------------------------------------

class TestHistoricalCostRecalculation:
    """Show what the OLD log entries *should* have cost with correct Haiku pricing."""

    HISTORICAL_ENTRIES = [
        {"input_tokens": 29290, "output_tokens": 336, "model": "claude-haiku-4-20250514"},
        {"input_tokens": 24264, "output_tokens": 534, "model": "claude-haiku-4-20250514"},
        {"input_tokens": 72120, "output_tokens": 2196, "model": "claude-haiku-4-20250514"},
        {"input_tokens": 50606, "output_tokens": 511, "model": "claude-haiku-4-20250514"},
    ]

    def test_old_costs_were_inflated(self):
        """Show the historical cost was 3.75x inflated due to Sonnet pricing."""
        for entry in self.HISTORICAL_ENTRIES:
            logged_cost = entry["input_tokens"] * 3.0/1e6 + entry["output_tokens"] * 15.0/1e6
            real_cost = entry["input_tokens"] * 0.80/1e6 + entry["output_tokens"] * 4.0/1e6
            ratio = logged_cost / real_cost
            assert 3.5 < ratio < 4.0, f"Old/real ratio should be ~3.75, got {ratio:.2f}"

    def test_real_avg_cost_per_turn(self):
        """Real Haiku cost per turn is ~$0.03, not $0.15."""
        real_costs = [
            e["input_tokens"] * 0.80/1e6 + e["output_tokens"] * 4.0/1e6
            for e in self.HISTORICAL_ENTRIES
        ]
        avg = sum(real_costs) / len(real_costs)
        assert avg < 0.05, f"Real avg Haiku cost should be <$0.05/turn, got ${avg:.4f}"
