"""Tests for Duel Mode backend (council.py)."""

import json

import pytest

from services.council import (
    DuelConfig,
    DuelScores,
    build_judge_prompt,
    build_round1_prompt,
    build_round2_prompt,
    parse_judge_verdict,
    validate_duel_config,
)

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


SPEC_A = {
    "id": "career-strategist",
    "name": "Career Strategist",
    "role": "Career advice expert",
    "icon": "💼",
    "rules": ["Be direct", "Focus on career growth"],
}
SPEC_B = {
    "id": "financial-planner",
    "name": "Financial Planner",
    "role": "Financial planning expert",
    "icon": "💰",
    "rules": [],
}

TOPIC = "Should I change jobs this year?"


# --- Config validation ---


def test_duel_config_validation_exactly_2():
    with pytest.raises(ValueError, match="exactly 2"):
        validate_duel_config(DuelConfig(topic=TOPIC, specialist_ids=["a"]))
    with pytest.raises(ValueError, match="exactly 2"):
        validate_duel_config(DuelConfig(topic=TOPIC, specialist_ids=["a", "b", "c"]))


def test_duel_config_validation_empty_topic():
    with pytest.raises(ValueError, match="empty"):
        validate_duel_config(DuelConfig(topic="", specialist_ids=["a", "b"]))
    with pytest.raises(ValueError, match="empty"):
        validate_duel_config(DuelConfig(topic="   ", specialist_ids=["a", "b"]))


def test_duel_config_validation_ok():
    validate_duel_config(DuelConfig(topic=TOPIC, specialist_ids=["a", "b"]))


# --- Prompt building ---


def test_round1_prompt_has_names_and_topic():
    prompt = build_round1_prompt(SPEC_A, SPEC_B, TOPIC, "Some notes context")
    assert SPEC_A["name"] in prompt
    assert SPEC_B["name"] in prompt
    assert TOPIC in prompt
    assert "Some notes context" in prompt
    assert "250 words" in prompt


def test_round1_prompt_includes_rules():
    prompt = build_round1_prompt(SPEC_A, SPEC_B, TOPIC, "")
    assert "Be direct" in prompt
    assert "Focus on career growth" in prompt


def test_round2_prompt_includes_opponent_r1():
    prompt = build_round2_prompt(
        SPEC_A, SPEC_B, TOPIC,
        own_r1="My first argument.",
        opponent_r1="Opponent's first argument.",
    )
    assert "Opponent's first argument." in prompt
    assert "My first argument." in prompt
    assert "200 words" in prompt
    assert "Counter-Arguments" in prompt


def test_judge_prompt_has_all_statements():
    r1 = {SPEC_A["id"]: "A Round 1", SPEC_B["id"]: "B Round 1"}
    r2 = {SPEC_A["id"]: "A Round 2", SPEC_B["id"]: "B Round 2"}
    prompt = build_judge_prompt(TOPIC, SPEC_A, SPEC_B, r1, r2)
    assert "A Round 1" in prompt
    assert "B Round 1" in prompt
    assert "A Round 2" in prompt
    assert "B Round 2" in prompt
    assert "relevance" in prompt
    assert "evidence" in prompt
    assert "actionability" in prompt
    assert SPEC_A["id"] in prompt
    assert SPEC_B["id"] in prompt


# --- Verdict parsing ---


def test_parse_judge_verdict_valid():
    json_str = json.dumps({
        "scores": {
            "career-strategist": {
                "relevance": 4, "evidence": 3, "argument_strength": 4,
                "counter_argument": 3, "actionability": 4,
            },
            "financial-planner": {
                "relevance": 4, "evidence": 5, "argument_strength": 4,
                "counter_argument": 4, "actionability": 5,
            },
        },
        "winner": "financial-planner",
        "reasoning": "Stronger evidence and actionable advice.",
        "recommendation": "Consider both perspectives.",
        "action_items": ["Review budget", "Update resume"],
    })
    verdict = parse_judge_verdict(json_str, SPEC_A, SPEC_B)
    assert isinstance(verdict, DuelScores)
    assert verdict.winner == "financial-planner"
    assert verdict.reasoning == "Stronger evidence and actionable advice."
    assert len(verdict.action_items) == 2
    assert sum(verdict.scores["financial-planner"].values()) == 22
    assert sum(verdict.scores["career-strategist"].values()) == 18


def test_parse_judge_verdict_with_markdown_fence():
    json_str = "```json\n" + json.dumps({
        "scores": {
            "career-strategist": {"relevance": 3, "evidence": 3, "argument_strength": 3, "counter_argument": 3, "actionability": 3},
            "financial-planner": {"relevance": 4, "evidence": 4, "argument_strength": 4, "counter_argument": 4, "actionability": 4},
        },
        "winner": "financial-planner",
        "reasoning": "Better overall.",
        "recommendation": "Go with finances.",
        "action_items": [],
    }) + "\n```"
    verdict = parse_judge_verdict(json_str, SPEC_A, SPEC_B)
    assert verdict.winner == "financial-planner"


def test_parse_judge_verdict_invalid_json():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_judge_verdict("This is not JSON at all", SPEC_A, SPEC_B)


def test_parse_judge_verdict_invalid_winner_falls_back():
    """If winner is not a valid specialist id, pick by higher score."""
    json_str = json.dumps({
        "scores": {
            "career-strategist": {"relevance": 5, "evidence": 5, "argument_strength": 5, "counter_argument": 5, "actionability": 5},
            "financial-planner": {"relevance": 3, "evidence": 3, "argument_strength": 3, "counter_argument": 3, "actionability": 3},
        },
        "winner": "unknown-id",
        "reasoning": "Unclear.",
        "recommendation": "Both ok.",
        "action_items": [],
    })
    verdict = parse_judge_verdict(json_str, SPEC_A, SPEC_B)
    assert verdict.winner == "career-strategist"


# --- Memory save ---


@pytest.mark.anyio
async def test_duel_memory_save(tmp_path):
    from models.database import init_database
    from services.council import save_duel_to_memory

    ws = tmp_path
    (ws / "memory" / "decisions").mkdir(parents=True)
    (ws / "app").mkdir(parents=True)
    (ws / "graph").mkdir(parents=True)
    await init_database(ws / "app" / "jarvis.db")

    config = DuelConfig(topic=TOPIC, specialist_ids=[SPEC_A["id"], SPEC_B["id"]])
    r1 = {SPEC_A["id"]: "Career argument", SPEC_B["id"]: "Finance argument"}
    r2 = {SPEC_A["id"]: "Career rebuttal", SPEC_B["id"]: "Finance rebuttal"}
    verdict = DuelScores(
        specialist_a_id=SPEC_A["id"],
        specialist_b_id=SPEC_B["id"],
        scores={
            SPEC_A["id"]: {"relevance": 4, "evidence": 3, "argument_strength": 4, "counter_argument": 3, "actionability": 4},
            SPEC_B["id"]: {"relevance": 4, "evidence": 5, "argument_strength": 4, "counter_argument": 4, "actionability": 5},
        },
        winner=SPEC_B["id"],
        reasoning="Better evidence.",
        recommendation="Consider financial stability.",
        action_items=["Review budget"],
    )

    path = await save_duel_to_memory(config, SPEC_A, SPEC_B, r1, r2, verdict, ws)

    assert path.startswith("decisions/")
    assert "duel" in path

    # Check file exists and has correct content
    file_path = ws / "memory" / path
    assert file_path.exists()
    content = file_path.read_text()
    assert "duel-debate" in content
    assert "financial-planner" in content
    assert "Career argument" in content
    assert "Finance rebuttal" in content
    assert "Better evidence." in content


# --- WS event sequence ---


def test_duel_event_sequence():
    """Verify the expected event types exist in the module."""
    from services.council import DuelEvent

    events = [
        DuelEvent(type="setup"),
        DuelEvent(type="round_start", round_num=1),
        DuelEvent(type="specialist_start", specialist="A", round_num=1),
        DuelEvent(type="specialist_delta", specialist="A", content="text", round_num=1),
        DuelEvent(type="specialist_done", specialist="A", round_num=1),
        DuelEvent(type="judge_start"),
        DuelEvent(type="judge_done", metadata={"scores": {}}),
        DuelEvent(type="done", metadata={"saved_path": ""}),
        DuelEvent(type="error", content="oops"),
    ]
    types = [e.type for e in events]
    assert "setup" in types
    assert "round_start" in types
    assert "judge_done" in types
    assert "done" in types
