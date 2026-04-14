# Step 16a — Duel Mode: Backend (Orchestrator, Prompts, Scoring, Memory)

> **Goal**: Build the complete Duel backend — DuelOrchestrator that runs 2 rounds
> of debate between 2 specialists, Jarvis as judge with 5-criteria scoring,
> WebSocket event streaming, and duel result saved to memory + graph.

**Status**: ⬜ Not started
**Depends on**: Step 15 (feedback loops — especially 15a auto-graph)

---

## Core Principles (from parent spec)

1. **Duel is a chat feature** — runs through existing chat WebSocket
2. **Argumentative, not collaborative** — prompts force challenging/rebutting
3. **Jarvis is judge, not participant** — scores on 5 explicit criteria
4. **2 rounds** — positions then counter-arguments
5. **Structured verdict** — JSON with scores, winner, reasoning, action items

---

## MVP Constraints (Hard Rules)

> **Risk**: Duel is expensive (5 API calls) and slow (~30s). These constraints
> prevent scope creep and keep cost/latency predictable.

| Constraint | Value | Rationale |
|-----------|-------|----------|
| **Max specialists** | **2 (hard cap)** | More specialists = exponential cost/complexity. 3+ is Council (step 17). |
| **Max rounds** | **2** | Diminishing returns after R2. Keep debates tight. |
| **R1 max words** | **250** | Force concise opening — no essays |
| **R2 max words** | **200** | Counter-arguments should be sharper, not longer |
| **Total token budget** | **~15,600** | ~$0.06 Sonnet. Hard fail if > 25,000 tokens total. |
| **Timeout** | **60s** | If any single API call takes > 60s, abort with error |
| **No auto-trigger** | — | User must explicitly start a duel. No "Jarvis suggests duel". |

These are not suggestions — enforce them in code with validation.

```python
def validate_duel_config(config: DuelConfig) -> None:
    if len(config.specialist_ids) != 2:
        raise ValueError("Duel requires exactly 2 specialists")
    if not config.topic.strip():
        raise ValueError("Duel topic cannot be empty")
```

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `council.py` service | DuelOrchestrator, data models, prompt builders |
| System prompts | Round 1 (position), Round 2 (counter-argument), Judge (verdict) |
| Scoring | 5 criteria × 1-5 scale, JSON output from judge |
| WebSocket events | `duel_*` events through existing chat WS |
| Memory save | `duel-debate` note in `memory/decisions/` |
| Graph edges | `debated_by` + `won_by` edges |

**What this step does NOT cover** (deferred to 16b):
- DuelSetup.vue, DuelDebateView.vue, DuelScoreBar.vue
- useDuel.ts composable
- Chat input bar ⚔️ button
- Score bar visualization
- Any frontend changes

---

## File Structure

```
backend/
├── services/
│   └── council.py              # NEW — DuelOrchestrator + prompts + scoring
├── routers/
│   └── chat.py                 # MODIFY — add duel_start WS handler
├── tests/
│   └── test_duel_backend.py    # NEW — orchestrator + scoring tests
```

---

## Data Models

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class DuelConfig:
    topic: str
    specialist_ids: list  # exactly 2
    mode: str = "duel"

@dataclass
class DuelEvent:
    type: str       # "setup" | "round_start" | "specialist_start" |
                    # "specialist_delta" | "specialist_done" |
                    # "judge_start" | "judge_done" | "done" | "error"
    specialist: str = ""
    content: str = ""
    round_num: int = 1
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
    round1: dict            # {specialist_id: response_text}
    round2: dict            # {specialist_id: response_text}
    verdict: Optional[DuelScores] = None
    status: str = "pending" # pending | round1 | round2 | judging | done | error
    token_usage: dict = field(default_factory=dict)
    created_at: str = ""
```

---

## System Prompts

### Round 1 — Opening Position

```python
DUEL_ROUND1_PROMPT = """You are {name}, participating in an intellectual duel.

YOUR ROLE: {role}
{rules_section}

## Duel Context

TOPIC: {topic}
OPPONENT: {opponent_name} ({opponent_role})

This is Round 1 — Opening Positions.
You are presenting your expert perspective. Your opponent will do the same.
In Round 2, you will each challenge the other's arguments.

## User's Relevant Notes
{shared_context}

{specialist_knowledge_section}

## Your Task — Round 1
1. State your position clearly (1–2 sentence thesis)
2. Support with 2–3 specific arguments from your domain
3. Reference the user's notes to ground your advice
4. Flag 1 risk or blind spot the opponent's perspective might have

CONSTRAINTS:
- Max 250 words
- Be direct and opinionated — this is a duel, not a committee
- Do NOT try to be balanced — that's the judge's job
- Do NOT use generic advice — tie everything to the user's situation
- Argue to WIN — your opponent will try to dismantle your argument"""
```

### Round 2 — Counter-Argument

```python
DUEL_ROUND2_PROMPT = """You are {name}, continuing an intellectual duel.

YOUR ROLE: {role}
{rules_section}

## Duel Context

TOPIC: {topic}
OPPONENT: {opponent_name}

This is Round 2 — Counter-Arguments.
Your opponent said this in Round 1:

--- OPPONENT'S ARGUMENT ---
{opponent_round1_statement}
--- END ---

Your own Round 1 position:
--- YOUR ARGUMENT ---
{own_round1_statement}
--- END ---

## Your Task — Round 2
1. Identify the WEAKEST point in your opponent's argument
2. Explain specifically why it's weak (logic gap, missing data, wrong assumption)
3. Explain why YOUR perspective better serves the user on that point
4. If your opponent made a genuinely strong point, concede it — then explain
   why your overall position still holds

CONSTRAINTS:
- Max 200 words
- Do NOT repeat your Round 1 arguments — build on them
- Directly engage with what the opponent said — quote or reference specifics
- Be intellectually honest — conceding a good point shows strength
- This is your last word — make it count"""
```

### Jarvis Judge

```python
DUEL_JUDGE_PROMPT = """You are Jarvis, judging an intellectual duel between two specialists.

The user asked: "{topic}"

## The Duel

### {specialist_a_name} ({specialist_a_role})

**Round 1 — Position:**
{specialist_a_round1}

**Round 2 — Counter-argument:**
{specialist_a_round2}

### {specialist_b_name} ({specialist_b_role})

**Round 1 — Position:**
{specialist_b_round1}

**Round 2 — Counter-argument:**
{specialist_b_round2}

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
    "{specialist_a_id}": {{
      "relevance": <1-5>, "evidence": <1-5>, "argument_strength": <1-5>,
      "counter_argument": <1-5>, "actionability": <1-5>
    }},
    "{specialist_b_id}": {{
      "relevance": <1-5>, "evidence": <1-5>, "argument_strength": <1-5>,
      "counter_argument": <1-5>, "actionability": <1-5>
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
```

---

## DuelOrchestrator

```python
class DuelOrchestrator:
    def __init__(self, claude_service):
        self.claude = claude_service

    async def run(self, config, workspace_path):
        """Run a 2-round duel with judge verdict. Yields DuelEvents."""

        # 1. Load 2 specialists
        spec_a = specialist_service.get_specialist(config.specialist_ids[0])
        spec_b = specialist_service.get_specialist(config.specialist_ids[1])

        # 2. Build shared context
        shared_context, _ = await build_context(config.topic, workspace_path=workspace_path)

        yield DuelEvent(type="setup", metadata={...})

        # ── ROUND 1 ──
        yield DuelEvent(type="round_start", round_num=1, metadata={"label": "Opening Positions"})
        round1 = {}
        for spec, opponent in [(spec_a, spec_b), (spec_b, spec_a)]:
            # Stream position via Claude, yield deltas
            ...
            round1[spec["id"]] = response

        # ── ROUND 2 ──
        yield DuelEvent(type="round_start", round_num=2, metadata={"label": "Counter-Arguments"})
        round2 = {}
        for spec, opponent in [(spec_a, spec_b), (spec_b, spec_a)]:
            # Stream counter-argument with opponent's R1 in prompt
            ...
            round2[spec["id"]] = response

        # ── VERDICT ──
        yield DuelEvent(type="judge_start")
        judge_response = ""  # Collect full judge response
        verdict = parse_judge_verdict(judge_response, spec_a, spec_b)
        yield DuelEvent(type="judge_done", metadata={scores, winner, reasoning, ...})

        # ── SAVE ──
        saved_path = await save_duel_to_memory(config, spec_a, spec_b, round1, round2, verdict, workspace_path)
        yield DuelEvent(type="done", metadata={"saved_path": saved_path})
```

Full implementation code is in the parent spec ([step-16-council-lite.md](step-16-council-lite.md)).

---

## WebSocket Integration

### Frontend → Backend

```json
{"type": "duel_start", "topic": "...", "specialist_ids": ["id-a", "id-b"]}
```

### Backend → Frontend (event stream)

```json
{"type": "duel_setup", "specialists": [...], "topic": "..."}
{"type": "duel_round_start", "round": 1, "label": "Opening Positions"}
{"type": "duel_specialist_start", "specialist": "Career Strategist", "round": 1}
{"type": "duel_specialist_delta", "specialist": "Career Strategist", "content": "...", "round": 1}
{"type": "duel_specialist_done", "specialist": "Career Strategist", "round": 1}
... (repeat for specialist B, then round 2, then judge)
{"type": "duel_judge_done", "scores": {...}, "winner": "...", "reasoning": "..."}
{"type": "duel_done", "saved_path": "decisions/..."}
```

### `routers/chat.py` changes

```python
if data.get("type") == "duel_start":
    await _handle_duel(websocket, data, session_id, workspace_path)
    return
```

---

## Memory Save

### Frontmatter

```yaml
---
title: "Duel: Should I change jobs?"
type: duel-debate
date: 2026-04-14
specialists: [career-strategist, financial-planner]
winner: financial-planner
scores: {career-strategist: 18, financial-planner: 22}
tags: [career, decision, duel]
---
```

### Save location: `memory/decisions/{date}-duel-{topic-slug}.md`

### Graph edges

```python
graph_service.add_edge(note_id, f"specialist:{spec_id}", "debated_by", weight=0.9)
graph_service.add_edge(note_id, f"specialist:{winner}", "won_by", weight=1.0)
```

Duel nodes use **amber/gold color** in graph.

---

## Token Budget

| Component | Tokens (est.) |
|-----------|--------------|
| 2 × Round 1 prompts | ~5000 |
| 2 × Round 1 responses | ~1400 |
| 2 × Round 2 prompts | ~4000 |
| 2 × Round 2 responses | ~1200 |
| Judge prompt | ~3500 |
| Judge response | ~500 |
| **Total** | **~15,600** |
| **Cost (Sonnet)** | **~$0.06** |

5 Claude API calls total.

**Cost guardrail**: If total tokens exceed 25,000, log a warning. Never silently
spend more than ~$0.10 on a single duel. If user's token tracking shows they've
spent > $1 on duels in a session, show a cost warning (deferred to 16b frontend).

---

## Tests

```
test_duel_config_validation        — exactly 2 specialist_ids required
test_round1_prompt_building        — correct specialist/opponent names, context injected
test_round2_prompt_building        — opponent's R1 statement included in prompt
test_judge_prompt_building         — all 4 statements included
test_parse_judge_verdict_valid     — valid JSON → DuelScores object
test_parse_judge_verdict_invalid   — no JSON → ValueError raised
test_duel_memory_save_frontmatter  — correct type, winner, scores in frontmatter
test_duel_memory_save_body         — all rounds + verdict in markdown body
test_duel_graph_edges              — debated_by + won_by edges created
test_duel_ws_event_sequence        — events come in correct order
```

---

## Verification (Manual)

After implementation, test with curl/websocat against the WS endpoint:
1. Send `duel_start` message
2. Verify events stream in correct order: setup → round1 specialists → round2 specialists → judge → done
3. Verify `memory/decisions/` file created with correct frontmatter
4. Verify graph has duel node + edges

---

## Definition of Done

- [ ] `services/council.py` created with DuelOrchestrator, data models, prompt builders
- [ ] Round 1 prompts force opinionated positions (not balanced)
- [ ] Round 2 prompts include opponent's R1 and force direct rebuttal
- [ ] Judge prompt uses 5 explicit criteria, outputs structured JSON
- [ ] `parse_judge_verdict` parses JSON correctly with error handling
- [ ] WS handler in `chat.py` routes `duel_start` to orchestrator
- [ ] All `duel_*` events stream through existing chat WebSocket
- [ ] Duel result saved to `memory/decisions/` with `type: duel-debate` frontmatter
- [ ] Graph edges created: `debated_by` (both specialists) + `won_by` (winner)
- [ ] Verdict summary added to session history (for continued chat)
- [ ] All tests pass (10 test cases)
