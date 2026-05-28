"""Tests for tool_result compaction + soft-cap helpers in routers.chat."""

from routers.chat import (
    _STALE_TOOL_RESULT_CAP,
    _TOOL_RESULT_SOFT_CAP,
    _compact_stale_tool_results,
    _truncate_tool_result,
)


def test_truncate_short_text_unchanged():
    text = "small payload"
    assert _truncate_tool_result(text, 1000) == text


def test_truncate_large_text_keeps_head_and_tail():
    text = "A" * 5000 + "B" * 5000
    out = _truncate_tool_result(text, 2000)
    assert len(out) < len(text)
    assert out.startswith("A")
    assert out.endswith("B")
    assert "truncated" in out


def test_soft_cap_default_is_reasonable():
    # Sanity: the cap leaves room for a meaningful head+tail
    assert _TOOL_RESULT_SOFT_CAP >= 2000
    assert _STALE_TOOL_RESULT_CAP < _TOOL_RESULT_SOFT_CAP


def _msg(tool_use_id: str, result: str) -> list[dict]:
    return [
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": tool_use_id, "name": "read_note", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id, "content": result}],
        },
    ]


def test_compaction_noop_with_single_tool_result():
    messages = [{"role": "user", "content": "Hi"}] + _msg("t1", "X" * 5000)
    out = _compact_stale_tool_results(messages)
    # Only one tool_result — nothing to compact
    assert out[-1]["content"][0]["content"] == "X" * 5000


def test_compaction_keeps_last_two_intact():
    # Step 30e: multi-tool chains commonly reference results from 1–2 hops
    # back. We keep the last two tool_results intact; only earlier ones get
    # compacted.
    messages = (
        [{"role": "user", "content": "Start"}]
        + _msg("t1", "OLD" * 2000)  # oldest — should be compacted
        + _msg("t2", "MID" * 2000)  # second-to-last — kept intact
        + _msg("t3", "NEW" * 2000)  # latest — kept intact
    )
    out = _compact_stale_tool_results(messages)

    tool_results = [
        block
        for msg in out
        if msg.get("role") == "user" and isinstance(msg.get("content"), list)
        for block in msg["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    assert len(tool_results) == 3
    # Older compacted
    assert len(tool_results[0]["content"]) <= _STALE_TOOL_RESULT_CAP + 100
    # Last two intact
    assert tool_results[1]["content"] == "MID" * 2000
    assert tool_results[2]["content"] == "NEW" * 2000


def test_compaction_two_results_both_kept():
    # With only two tool_results, both are within the "keep last 2" window.
    messages = (
        [{"role": "user", "content": "Start"}]
        + _msg("t1", "OLD" * 2000)
        + _msg("t2", "NEW" * 2000)
    )
    out = _compact_stale_tool_results(messages)
    tool_results = [
        block
        for msg in out
        if msg.get("role") == "user" and isinstance(msg.get("content"), list)
        for block in msg["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]
    assert len(tool_results) == 2
    assert tool_results[0]["content"] == "OLD" * 2000
    assert tool_results[1]["content"] == "NEW" * 2000
