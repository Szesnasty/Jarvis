"""Duel Mode — two specialists debate, Jarvis judges.

Yields DuelEvent objects via an async generator so the WebSocket handler
can forward them to the frontend in real time.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional

from services.claude import ClaudeService, StreamEvent
from services.context_builder import build_context
from services.token_tracking import log_usage

logger = logging.getLogger(__name__)

# ── Hard limits (from spec) ──────────────────────────────────────────────────

MAX_SPECIALISTS = 2
MAX_ROUNDS = 2
R1_MAX_WORDS = 250
R2_MAX_WORDS = 200
TOTAL_TOKEN_BUDGET = 25_000
CALL_TIMEOUT_SECONDS = 60

# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class DuelConfig:
    topic: str
    specialist_ids: list  # exactly 2
    mode: str = "duel"


@dataclass
class DuelEvent:
    type: str       # setup | round_start | specialist_start | specialist_delta |
    # specialist_done | judge_start | judge_done | done | error
    specialist: str = ""
    content: str = ""
    round_num: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class DuelScores:
    specialist_a_id: str
    specialist_b_id: str
    scores: dict            # {specialist_id: {criterion: score}}
    winner: str             # specialist_id
    reasoning: str
    recommendation: str
    action_items: list


@dataclass
class DuelSession:
    id: str
    config: DuelConfig
    round1: dict = field(default_factory=dict)   # {specialist_id: response_text}
    round2: dict = field(default_factory=dict)   # {specialist_id: response_text}
    verdict: Optional[DuelScores] = None
    status: str = "pending"
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    created_at: str = ""


# ── Validation ───────────────────────────────────────────────────────────────


def validate_duel_config(config: DuelConfig) -> None:
    if len(config.specialist_ids) != MAX_SPECIALISTS:
        raise ValueError(f"Duel requires exactly {MAX_SPECIALISTS} specialists")
    if not config.topic.strip():
        raise ValueError("Duel topic cannot be empty")
    if len(config.topic) > 500:
        raise ValueError("Topic too long (max 500 chars)")


# ── Prompt builders ──────────────────────────────────────────────────────────


def build_round1_prompt(
    spec: dict, opponent: dict, topic: str, shared_context: str,
) -> str:
    rules_section = ""
    if spec.get("rules"):
        rules_section = "YOUR RULES:\n" + "\n".join(f"- {r}" for r in spec["rules"])

    knowledge_section = ""
    if spec.get("_knowledge"):
        knowledge_section = f"\n## Your Knowledge Sources\n{spec['_knowledge']}"

    return f"""You are {spec['name']}, participating in an intellectual duel.

YOUR ROLE: {spec.get('role', '')}
{rules_section}

## Duel Context

TOPIC: {topic}
OPPONENT: {opponent['name']} ({opponent.get('role', '')})

This is Round 1 — Opening Positions.
You are presenting your expert perspective. Your opponent will do the same.
In Round 2, you will each challenge the other's arguments.

## User's Relevant Notes
{shared_context or 'No specific notes available.'}
{knowledge_section}

## Your Task — Round 1
1. State your position clearly (1–2 sentence thesis)
2. Support with 2–3 specific arguments from your domain
3. Reference the user's notes to ground your advice
4. Flag 1 risk or blind spot the opponent's perspective might have

CONSTRAINTS:
- Max {R1_MAX_WORDS} words
- Be direct and opinionated — this is a duel, not a committee
- Do NOT try to be balanced — that's the judge's job
- Do NOT use generic advice — tie everything to the user's situation
- Argue to WIN — your opponent will try to dismantle your argument"""


def build_round2_prompt(
    spec: dict, opponent: dict, topic: str,
    own_r1: str, opponent_r1: str,
) -> str:
    rules_section = ""
    if spec.get("rules"):
        rules_section = "YOUR RULES:\n" + "\n".join(f"- {r}" for r in spec["rules"])

    return f"""You are {spec['name']}, continuing an intellectual duel.

YOUR ROLE: {spec.get('role', '')}
{rules_section}

## Duel Context

TOPIC: {topic}
OPPONENT: {opponent['name']}

This is Round 2 — Counter-Arguments.
Your opponent said this in Round 1:

--- OPPONENT'S ARGUMENT ---
{opponent_r1}
--- END ---

Your own Round 1 position:
--- YOUR ARGUMENT ---
{own_r1}
--- END ---

## Your Task — Round 2
1. Identify the WEAKEST point in your opponent's argument
2. Explain specifically why it's weak (logic gap, missing data, wrong assumption)
3. Explain why YOUR perspective better serves the user on that point
4. If your opponent made a genuinely strong point, concede it — then explain \
why your overall position still holds

CONSTRAINTS:
- Max {R2_MAX_WORDS} words
- Do NOT repeat your Round 1 arguments — build on them
- Directly engage with what the opponent said — quote or reference specifics
- Be intellectually honest — conceding a good point shows strength
- This is your last word — make it count"""


def build_judge_prompt(
    topic: str,
    spec_a: dict, spec_b: dict,
    r1: dict, r2: dict,
) -> str:
    return f"""You are Jarvis, judging an intellectual duel between two specialists.

The user asked: "{topic}"

## The Duel

### {spec_a['name']} ({spec_a.get('role', '')})

**Round 1 — Position:**
{r1.get(spec_a['id'], '')}

**Round 2 — Counter-argument:**
{r2.get(spec_a['id'], '')}

### {spec_b['name']} ({spec_b.get('role', '')})

**Round 1 — Position:**
{r1.get(spec_b['id'], '')}

**Round 2 — Counter-argument:**
{r2.get(spec_b['id'], '')}

## Your Judgment

Evaluate both on 5 criteria (1–5 each):

1. **Relevance** — How well does the argument address the user's actual question?
2. **Evidence** — Does it reference the user's notes, data, or concrete facts?
3. **Argument strength** — Is the logic sound? Gaps? Unsupported leaps?
4. **Counter-argument quality** — Did Round 2 effectively challenge the opponent?
5. **Actionability** — Can the user act on these recommendations immediately?

Output ONLY valid JSON:

{{
  "scores": {{
    "{spec_a['id']}": {{
      "relevance": 0, "evidence": 0, "argument_strength": 0,
      "counter_argument": 0, "actionability": 0
    }},
    "{spec_b['id']}": {{
      "relevance": 0, "evidence": 0, "argument_strength": 0,
      "counter_argument": 0, "actionability": 0
    }}
  }},
  "winner": "<specialist_id>",
  "reasoning": "<2-3 sentences WHY this specialist won>",
  "recommendation": "<3-4 sentences balanced recommendation>",
  "action_items": ["<action 1>", "<action 2>", "<action 3>"]
}}

CONSTRAINTS:
- Output ONLY JSON — no preamble, no markdown
- Must have a winner (no ties)
- Reasoning must reference SPECIFIC debate points
- Action items must be concrete and time-bound"""


# ── Verdict parsing ──────────────────────────────────────────────────────────


def parse_judge_verdict(
    response_text: str, spec_a: dict, spec_b: dict,
) -> DuelScores:
    """Parse the judge's JSON verdict into a DuelScores object."""
    # Try to extract JSON from possibly wrapped text
    text = response_text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Judge did not return valid JSON: {exc}") from exc

    scores = data.get("scores", {})
    winner = data.get("winner", "")
    if winner not in (spec_a["id"], spec_b["id"]):
        # Pick the one with higher total score
        total_a = sum(scores.get(spec_a["id"], {}).values())
        total_b = sum(scores.get(spec_b["id"], {}).values())
        winner = spec_a["id"] if total_a >= total_b else spec_b["id"]

    return DuelScores(
        specialist_a_id=spec_a["id"],
        specialist_b_id=spec_b["id"],
        scores=scores,
        winner=winner,
        reasoning=data.get("reasoning", ""),
        recommendation=data.get("recommendation", ""),
        action_items=data.get("action_items", []),
    )


# ── Memory save ──────────────────────────────────────────────────────────────


async def save_duel_to_memory(
    config: DuelConfig,
    spec_a: dict, spec_b: dict,
    r1: dict, r2: dict,
    verdict: DuelScores,
    workspace_path: Optional[Path] = None,
) -> str:
    """Save the duel result as a Markdown note in memory/decisions/."""
    from services import memory_service, graph_service
    from config import get_settings
    from utils.markdown import add_frontmatter

    ws = workspace_path or get_settings().workspace_path
    now = datetime.now(timezone.utc)

    slug = re.sub(r"[^a-z0-9]+", "-", config.topic.lower())[:40].strip("-")
    note_path = f"decisions/{now.strftime('%Y-%m-%d')}-duel-{slug}.md"

    # Calculate total scores
    total_a = sum(verdict.scores.get(spec_a["id"], {}).values())
    total_b = sum(verdict.scores.get(spec_b["id"], {}).values())

    fm = {
        "title": f"Duel: {config.topic}",
        "type": "duel-debate",
        "date": now.strftime("%Y-%m-%d"),
        "specialists": [spec_a["id"], spec_b["id"]],
        "winner": verdict.winner,
        "scores": {spec_a["id"]: total_a, spec_b["id"]: total_b},
        "tags": ["duel", "decision"],
    }

    # Build body
    parts = [
        f"## Topic\n\n{config.topic}\n",
        f"## Round 1 — Opening Positions\n",
        f"### {spec_a.get('icon', '🔹')} {spec_a['name']}\n\n{r1.get(spec_a['id'], '')}\n",
        f"### {spec_b.get('icon', '🔹')} {spec_b['name']}\n\n{r1.get(spec_b['id'], '')}\n",
        f"## Round 2 — Counter-Arguments\n",
        f"### {spec_a.get('icon', '🔹')} {spec_a['name']}\n\n{r2.get(spec_a['id'], '')}\n",
        f"### {spec_b.get('icon', '🔹')} {spec_b['name']}\n\n{r2.get(spec_b['id'], '')}\n",
        f"## Verdict\n",
        f"**Winner: {spec_a['name'] if verdict.winner == spec_a['id'] else spec_b['name']}**\n",
        f"{verdict.reasoning}\n",
        f"### Recommendation\n\n{verdict.recommendation}\n",
    ]
    if verdict.action_items:
        parts.append("### Action Items\n")
        for item in verdict.action_items:
            parts.append(f"- [ ] {item}")

    body = "\n".join(parts)
    content = add_frontmatter(body, fm)

    mem = ws / "memory"
    file_path = mem / note_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    # Index
    try:
        await memory_service.index_note_file(note_path, workspace_path=ws)
    except Exception:
        pass

    # Graph edges
    try:
        note_id = f"note:{note_path}"
        graph_service.ingest_note(note_path, ws)
        graph = graph_service.load_graph(ws)
        if graph:
            for sid in config.specialist_ids:
                spec_node = f"specialist:{sid}"
                graph.add_node(spec_node, "specialist", sid)
                graph.add_edge(note_id, spec_node, "debated_by", weight=0.9)
            graph.add_edge(
                note_id,
                f"specialist:{verdict.winner}",
                "won_by",
                weight=1.0,
            )
            graph_service._save_and_cache(graph, ws)
    except Exception:
        logger.warning("Failed to update graph for duel")

    return note_path


# ── Orchestrator ─────────────────────────────────────────────────────────────


class DuelOrchestrator:
    """Runs a 2-round duel between 2 specialists with a judge verdict."""

    def __init__(self, claude: ClaudeService):
        self.claude = claude

    async def run(
        self,
        config: DuelConfig,
        workspace_path: Optional[Path] = None,
    ) -> AsyncIterator[DuelEvent]:
        """Run the full duel. Yields DuelEvents for real-time streaming."""
        from services import specialist_service

        validate_duel_config(config)

        # 1. Load specialists
        spec_a = specialist_service.get_specialist(
            config.specialist_ids[0], workspace_path=workspace_path,
        )
        spec_b = specialist_service.get_specialist(
            config.specialist_ids[1], workspace_path=workspace_path,
        )
        if not spec_a or not spec_b:
            yield DuelEvent(type="error", content="One or both specialists not found")
            return

        # 2. Build shared context (retrieval)
        shared_context, _tokens = await build_context(
            config.topic, workspace_path=workspace_path,
        )

        session = DuelSession(
            id=uuid.uuid4().hex[:12],
            config=config,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        yield DuelEvent(
            type="setup",
            metadata={
                "duel_id": session.id,
                "specialists": [
                    {"id": spec_a["id"], "name": spec_a["name"], "icon": spec_a.get("icon", "🔹")},
                    {"id": spec_b["id"], "name": spec_b["name"], "icon": spec_b.get("icon", "🔹")},
                ],
                "topic": config.topic,
            },
        )

        # ── ROUND 1 ──────────────────────────────────────────────────────
        yield DuelEvent(
            type="round_start", round_num=1,
            metadata={"label": "Opening Positions"},
        )
        session.status = "round1"

        for spec, opponent in [(spec_a, spec_b), (spec_b, spec_a)]:
            prompt = build_round1_prompt(spec, opponent, config.topic, shared_context or "")

            yield DuelEvent(
                type="specialist_start",
                specialist=spec["name"], round_num=1,
            )

            text = ""
            async for event in self.claude.stream_response(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=f"You are {spec['name']}. {spec.get('role', '')}",
                tools=[],
            ):
                if event.type == "text_delta":
                    text += event.content
                    yield DuelEvent(
                        type="specialist_delta",
                        specialist=spec["name"],
                        content=event.content,
                        round_num=1,
                    )
                elif event.type == "usage":
                    session.token_usage["input"] += event.input_tokens
                    session.token_usage["output"] += event.output_tokens
                elif event.type == "error":
                    yield DuelEvent(type="error", content=f"{spec['name']} R1 error: {event.content}")
                    return

            session.round1[spec["id"]] = text
            yield DuelEvent(
                type="specialist_done",
                specialist=spec["name"], round_num=1,
            )

        # ── ROUND 2 ──────────────────────────────────────────────────────
        yield DuelEvent(
            type="round_start", round_num=2,
            metadata={"label": "Counter-Arguments"},
        )
        session.status = "round2"

        for spec, opponent in [(spec_a, spec_b), (spec_b, spec_a)]:
            prompt = build_round2_prompt(
                spec, opponent, config.topic,
                own_r1=session.round1.get(spec["id"], ""),
                opponent_r1=session.round1.get(opponent["id"], ""),
            )

            yield DuelEvent(
                type="specialist_start",
                specialist=spec["name"], round_num=2,
            )

            text = ""
            async for event in self.claude.stream_response(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=f"You are {spec['name']}. {spec.get('role', '')}",
                tools=[],
            ):
                if event.type == "text_delta":
                    text += event.content
                    yield DuelEvent(
                        type="specialist_delta",
                        specialist=spec["name"],
                        content=event.content,
                        round_num=2,
                    )
                elif event.type == "usage":
                    session.token_usage["input"] += event.input_tokens
                    session.token_usage["output"] += event.output_tokens
                elif event.type == "error":
                    yield DuelEvent(type="error", content=f"{spec['name']} R2 error: {event.content}")
                    return

            session.round2[spec["id"]] = text
            yield DuelEvent(
                type="specialist_done",
                specialist=spec["name"], round_num=2,
            )

        # ── VERDICT ───────────────────────────────────────────────────────
        yield DuelEvent(type="judge_start")
        session.status = "judging"

        judge_prompt = build_judge_prompt(
            config.topic, spec_a, spec_b,
            session.round1, session.round2,
        )

        judge_text = ""
        judge_error = ""
        async for event in self.claude.stream_response(
            messages=[{"role": "user", "content": judge_prompt}],
            system_prompt="You are Jarvis, an impartial judge. Output only valid JSON.",
            tools=[],
        ):
            if event.type == "text_delta":
                judge_text += event.content
            elif event.type == "usage":
                session.token_usage["input"] += event.input_tokens
                session.token_usage["output"] += event.output_tokens
            elif event.type == "error":
                judge_error = event.content

        if judge_error:
            logger.error("Judge API error: %s", judge_error)
            yield DuelEvent(type="error", content=f"Judge API error: {judge_error}")
            return

        if not judge_text.strip():
            logger.error("Judge returned empty response")
            yield DuelEvent(type="error", content="Judge returned empty response — please try again.")
            return

        logger.debug("Judge raw response: %s", judge_text[:500])

        try:
            verdict = parse_judge_verdict(judge_text, spec_a, spec_b)
            session.verdict = verdict
        except ValueError as exc:
            yield DuelEvent(type="error", content=f"Judge verdict parse error: {exc}")
            return

        # Token budget warning
        total_tokens = session.token_usage["input"] + session.token_usage["output"]
        if total_tokens > TOTAL_TOKEN_BUDGET:
            logger.warning(
                "Duel %s exceeded token budget: %d > %d",
                session.id, total_tokens, TOTAL_TOKEN_BUDGET,
            )

        # Log usage
        try:
            log_usage(session.token_usage["input"], session.token_usage["output"])
        except Exception:
            pass

        yield DuelEvent(
            type="judge_done",
            metadata={
                "scores": verdict.scores,
                "winner": verdict.winner,
                "reasoning": verdict.reasoning,
                "recommendation": verdict.recommendation,
                "action_items": verdict.action_items,
                "token_usage": session.token_usage,
            },
        )

        # ── SAVE ──────────────────────────────────────────────────────────
        session.status = "done"
        try:
            saved_path = await save_duel_to_memory(
                config, spec_a, spec_b,
                session.round1, session.round2,
                verdict, workspace_path,
            )
        except Exception as exc:
            logger.warning("Failed to save duel to memory: %s", exc)
            saved_path = ""

        yield DuelEvent(
            type="done",
            metadata={"saved_path": saved_path, "duel_id": session.id},
        )
