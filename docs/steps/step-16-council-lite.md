# Step 16 — Duel Mode: 2-Specialist Intellectual Debate

> **Goal**: Two specialists argue a topic across 2 rounds — positions then
> counter-arguments — with Jarvis as impartial judge who scores and declares
> a winner. All inside the existing chat interface.

**Status**: ⬜ Not started
**Depends on**: Step 15 (feedback loops — especially 15a auto-graph)

---

## Core Principles

1. **Duel is a chat feature, not a separate product.** No page navigation.
2. **Argumentative, not collaborative.** Specialists must challenge each other.
3. **Jarvis is the judge, not a third debater.** Scores on explicit criteria.
4. **Score bar, not vibes.** Each criterion scored 1–5, aggregated to percentage.
5. **Intellectual duel aesthetic.** Refined, elegant — not arena combat.

---

## File Structure

```
backend/
  services/
    council.py              # DuelOrchestrator + prompts + scoring
frontend/
  app/
    components/
      DuelSetup.vue         # Inline setup panel (topic + specialist picker)
      DuelDebateView.vue    # Live 2-round debate timeline
      DuelScoreBar.vue      # Criteria-based score visualization
    composables/
      useDuel.ts            # Duel state + WebSocket integration
```

No `pages/duel.vue`. Everything lives inside `main.vue`.

---

## The Duel — Two Rounds

### Round 1 — Opening Positions

Each specialist presents their position on the topic.
- State a clear thesis (1–2 sentences)
- Support with 2–3 domain-specific arguments
- Reference the user's notes to ground advice
- Flag 1 risk the opponent might miss

**Sequential streaming.** Specialist A finishes → Specialist B starts.
Both see only the shared context (user's notes), not each other's arguments yet.

### Round 2 — Counter-Arguments

Each specialist receives the opponent's Round 1 statement and must **directly challenge it**.
- Identify the weakest point in the opponent's argument
- Explain why their own perspective better serves the user
- Rebut with evidence or logic, not repetition
- Concede any point that is genuinely strong

**This is what makes it a duel.** Round 2 forces real intellectual engagement,
not two parallel monologues.

### Verdict — Jarvis as Judge

After both rounds, Jarvis evaluates both specialists against **5 explicit criteria**:

| # | Criterion | Description |
|---|-----------|-------------|
| 1 | **Relevance** | How well does the argument address the user's actual question? |
| 2 | **Evidence** | Does it reference the user's notes, data, or concrete facts? |
| 3 | **Argument strength** | Is the logic sound? Are there gaps or unsupported leaps? |
| 4 | **Counter-argument quality** | Did it effectively identify and challenge the opponent's weaknesses? |
| 5 | **Actionability** | Can the user act on these recommendations immediately? |

Each criterion: 1–5 scale. Total: 25 points max per specialist.
Mapped to a percentage for the score bar.

Jarvis declares a **winner** with reasoning: "Won because: stronger evidence
from your health notes, identified a real gap in the opponent's financial
assumptions, and gave you concrete next steps."

---

## UX Flow

### 1. Entry — From Chat

Input bar gets a duel trigger button:

```
┌─────────────────────────────────────┐
│  Talk to Jarvis...          🎤 ⚔️ ➤ │
└─────────────────────────────────────┘
```

The ⚔️ button opens **DuelSetup** inline (slides up above input bar).

Alternative entries:
- User types "/duel" or "let's debate..." → auto-opens setup
- If input has text, it pre-fills the topic

### 2. Setup — Inline Panel

```
┌─────────────────────────────────────────┐
│  ⚔️ Duel Mode                            │
│                                          │
│  Topic:                                  │
│  ┌──────────────────────────────────┐    │
│  │ Should I change jobs this year?  │    │
│  └──────────────────────────────────┘    │
│                                          │
│  Pick 2 specialists:                     │
│  [✓] 💼 Career Strategist               │
│  [✓] 💰 Financial Planner               │
│  [ ] 🧠 Personal Coach                  │
│                                          │
│  2 rounds · 5 scoring criteria           │
│  ~$0.08 · ~30s                           │
│                                          │
│  [Start Duel]  [Cancel]                  │
└─────────────────────────────────────────┘
```

Exactly 2 specialists. Cost estimate: `2 specialists × 2 rounds × ~3000 tokens + judge ~2000`.

### 3. During Duel — Chat Transforms

```
┌─────────────────────────────────────────┐
│  ⚔️ Duel — "Should I change jobs?"       │
│  Round 1 of 2 · Opening Positions        │
├─────────────────────────────────────────┤
│                                          │
│  💼 Career Strategist                    │
│  ┌──────────────────────────────────┐    │
│  │ Based on your notes about        │    │
│  │ dissatisfaction and Q2 market     │    │
│  │ data, now is optimal timing...    │    │
│  │ ▊                                 │    │
│  └──────────────────────────────────┘    │
│                                          │
│  💰 Financial Planner                    │
│  ┌──────────────────────────────────┐    │
│  │ ◌ Waiting for Round 1...          │    │
│  └──────────────────────────────────┘    │
│                                          │
│  [Cancel Duel]                           │
└─────────────────────────────────────────┘
```

After Round 1, the view transitions:

```
┌─────────────────────────────────────────┐
│  ⚔️ Duel — "Should I change jobs?"       │
│  Round 2 of 2 · Counter-Arguments        │
├─────────────────────────────────────────┤
│                                          │
│  Round 1 (collapsed)                     │
│  ├ 💼 Career Strategist ✓               │
│  └ 💰 Financial Planner ✓               │
│                                          │
│  💼 Career Strategist — Rebuttal         │
│  ┌──────────────────────────────────┐    │
│  │ The Financial Planner raises a    │    │
│  │ fair point about runway, but      │    │
│  │ ignores that your current salary  │    │
│  │ ceiling is...                     │    │
│  │ ▊                                 │    │
│  └──────────────────────────────────┘    │
│                                          │
│  💰 Financial Planner — Rebuttal         │
│  ┌──────────────────────────────────┐    │
│  │ ◌ Waiting for Round 2...          │    │
│  └──────────────────────────────────┘    │
│                                          │
└─────────────────────────────────────────┘
```

### 4. Verdict — Score Bar + Winner

After both rounds, Jarvis evaluates:

```
┌─────────────────────────────────────────┐
│  ⚔️ Verdict                              │
│                                          │
│  ┌──────────────────────────────────┐    │
│  │                                   │    │
│  │  💼 Career     42%  ░░░░████████  │    │
│  │  Strategist         ████████░░░░  │    │
│  │                          58%  💰  │    │
│  │                  Financial Planner│    │
│  │                                   │    │
│  └──────────────────────────────────┘    │
│                                          │
│  Criteria Breakdown:                     │
│  ┌──────────────────────────────────┐    │
│  │  Relevance      ████░  │ ████░   │    │
│  │  Evidence        ███░░  │ █████   │    │
│  │  Argument        ████░  │ ████░   │    │
│  │  Counter-arg     ███░░  │ ████░   │    │
│  │  Actionability   ███░░  │ █████   │    │
│  │                   💼      💰      │    │
│  └──────────────────────────────────┘    │
│                                          │
│  🏆 Winner: Financial Planner            │
│  "Stronger evidence from your savings    │
│   data, identified a real gap in the     │
│   career argument about timing, and      │
│   gave concrete 6-month action plan."    │
│                                          │
│  📝 Saved to memory · 🔗 Graph updated   │
└─────────────────────────────────────────┘
```

The score bar shows **relative strength**, not absolute. If both score 20/25,
the bar is nearly 50/50. If one scores 22 and the other 15, it's clearly skewed.

### 5. After Verdict — Back to Chat

Duel view fades. A **duel result message** is appended to chat history with
the verdict, score summary, and winner reasoning. User continues chatting:
"Tell me more about the financial runway argument" — Jarvis has full context.

---

## System Prompts

### Round 1 — Opening Position Prompt

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

### Round 2 — Counter-Argument Prompt

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

### Jarvis Judge Prompt

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

You are the JUDGE, not a participant. Evaluate both specialists on these 5 criteria.
Score each 1–5 (1=poor, 5=excellent):

### Scoring Criteria

1. **Relevance** — How well does the argument address the user's actual question?
2. **Evidence** — Does it reference the user's notes, data, or concrete facts?
3. **Argument strength** — Is the logic sound? Gaps? Unsupported leaps?
4. **Counter-argument quality** — Did Round 2 effectively challenge the opponent?
5. **Actionability** — Can the user act on these recommendations immediately?

### Required Output Format (STRICT — follow exactly)

IMPORTANT: Output ONLY valid JSON. No markdown, no preamble, no explanation outside JSON.

{{
  "scores": {{
    "{specialist_a_id}": {{
      "relevance": <1-5>,
      "evidence": <1-5>,
      "argument_strength": <1-5>,
      "counter_argument": <1-5>,
      "actionability": <1-5>
    }},
    "{specialist_b_id}": {{
      "relevance": <1-5>,
      "evidence": <1-5>,
      "argument_strength": <1-5>,
      "counter_argument": <1-5>,
      "actionability": <1-5>
    }}
  }},
  "winner": "<specialist_id>",
  "reasoning": "<2-3 sentences explaining WHY this specialist won>",
  "recommendation": "<3-4 sentences: balanced recommendation incorporating both>",
  "action_items": ["<concrete action 1>", "<action 2>", "<action 3>"]
}}

CONSTRAINTS:
- Output ONLY the JSON block — no preamble, no markdown outside the json
- Be decisive — there MUST be a winner (no ties)
- Reasoning must reference SPECIFIC points from the debate
- Do not invent arguments neither specialist made
- Action items must be concrete and time-bound"""
```

### Why Two Rounds Matter

Round 1 alone produces **parallel monologues** — each specialist talks past the other.
Round 2 forces **direct engagement**: "You said X, but that ignores Y because Z."

This creates genuine intellectual tension the judge can evaluate.
Without Round 2, the judge is just comparing two independent essays.
With Round 2, the judge sees how each thinker handles pressure and criticism.

---

## Backend: `services/council.py`

### Data Model

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

### DuelOrchestrator

```python
class DuelOrchestrator:
    def __init__(self, claude_service):
        self.claude = claude_service

    async def run(self, config, workspace_path):
        """Run a 2-round duel with judge verdict."""

        # 1. Load the 2 specialists
        spec_a = specialist_service.get_specialist(config.specialist_ids[0])
        spec_b = specialist_service.get_specialist(config.specialist_ids[1])

        # 2. Build shared context from user's notes
        shared_context, _ = await build_context(
            config.topic, workspace_path=workspace_path,
        )

        yield DuelEvent(type="setup", metadata={
            "topic": config.topic,
            "specialists": [spec_a["name"], spec_b["name"]],
        })

        # ── ROUND 1: Opening Positions ──
        yield DuelEvent(type="round_start", round_num=1,
                        metadata={"label": "Opening Positions"})

        round1 = {}
        for spec, opponent in [(spec_a, spec_b), (spec_b, spec_a)]:
            yield DuelEvent(type="specialist_start",
                            specialist=spec["name"], round_num=1)

            prompt = build_round1_prompt(
                specialist=spec, opponent=opponent,
                topic=config.topic,
                shared_context=shared_context,
                workspace_path=workspace_path,
            )

            response = ""
            async for event in self.claude.stream_response(
                messages=[{"role": "user", "content": config.topic}],
                system_prompt=prompt,
                tools=[],
            ):
                if event.type == "text_delta":
                    response += event.content
                    yield DuelEvent(type="specialist_delta",
                                    specialist=spec["name"],
                                    content=event.content, round_num=1)

            round1[spec["id"]] = response
            yield DuelEvent(type="specialist_done",
                            specialist=spec["name"], round_num=1)

        # ── ROUND 2: Counter-Arguments ──
        yield DuelEvent(type="round_start", round_num=2,
                        metadata={"label": "Counter-Arguments"})

        round2 = {}
        for spec, opponent in [(spec_a, spec_b), (spec_b, spec_a)]:
            yield DuelEvent(type="specialist_start",
                            specialist=spec["name"], round_num=2)

            prompt = build_round2_prompt(
                specialist=spec, opponent=opponent,
                topic=config.topic,
                own_round1=round1[spec["id"]],
                opponent_round1=round1[opponent["id"]],
                workspace_path=workspace_path,
            )

            response = ""
            async for event in self.claude.stream_response(
                messages=[{"role": "user", "content":
                          f"Counter-argue against {opponent['name']}."}],
                system_prompt=prompt,
                tools=[],
            ):
                if event.type == "text_delta":
                    response += event.content
                    yield DuelEvent(type="specialist_delta",
                                    specialist=spec["name"],
                                    content=event.content, round_num=2)

            round2[spec["id"]] = response
            yield DuelEvent(type="specialist_done",
                            specialist=spec["name"], round_num=2)

        # ── VERDICT: Jarvis as Judge ──
        yield DuelEvent(type="judge_start")

        judge_prompt = build_judge_prompt(
            topic=config.topic,
            spec_a=spec_a, spec_b=spec_b,
            round1=round1, round2=round2,
        )

        judge_response = ""
        async for event in self.claude.stream_response(
            messages=[{"role": "user", "content": "Judge this duel."}],
            system_prompt=judge_prompt,
            tools=[],
        ):
            if event.type == "text_delta":
                judge_response += event.content

        # Parse structured verdict
        verdict = parse_judge_verdict(judge_response, spec_a, spec_b)

        yield DuelEvent(type="judge_done", metadata={
            "scores": verdict.scores,
            "winner": verdict.winner,
            "reasoning": verdict.reasoning,
            "recommendation": verdict.recommendation,
            "action_items": verdict.action_items,
        })

        # Save to memory
        saved_path = await save_duel_to_memory(
            config, spec_a, spec_b, round1, round2, verdict, workspace_path,
        )

        yield DuelEvent(type="done", metadata={"saved_path": saved_path})


def parse_judge_verdict(raw_response, spec_a, spec_b):
    """Parse JSON from judge response, with fallback."""
    import json, re
    match = re.search(r'\{[\s\S]*\}', raw_response)
    if not match:
        raise ValueError("Judge did not return valid JSON")
    data = json.loads(match.group())
    return DuelScores(
        specialist_a_id=spec_a["id"],
        specialist_b_id=spec_b["id"],
        scores=data["scores"],
        winner=data["winner"],
        reasoning=data["reasoning"],
        recommendation=data.get("recommendation", ""),
        action_items=data.get("action_items", []),
    )
```

### Context Strategy (Token Optimization)

```python
def build_round1_prompt(specialist, opponent, topic, shared_context, workspace_path):
    """Round 1: opening position. No opponent arguments yet."""
    core = truncate_to_tokens(shared_context, 1500)
    spec_context = load_specialist_sources(specialist, workspace_path, max_tokens=1000)
    return DUEL_ROUND1_PROMPT.format(
        name=specialist["name"],
        role=specialist.get("role", "Expert advisor"),
        rules_section=format_rules(specialist),
        topic=topic,
        opponent_name=opponent["name"],
        opponent_role=opponent.get("role", "Expert advisor"),
        shared_context=core,
        specialist_knowledge_section=(
            f"## Your Specialist Knowledge\n{spec_context}" if spec_context else ""
        ),
    )

def build_round2_prompt(specialist, opponent, topic, own_round1, opponent_round1, workspace_path):
    """Round 2: counter-arguments. Has both Round 1 statements."""
    return DUEL_ROUND2_PROMPT.format(
        name=specialist["name"],
        role=specialist.get("role", "Expert advisor"),
        rules_section=format_rules(specialist),
        topic=topic,
        opponent_name=opponent["name"],
        opponent_round1_statement=opponent_round1,
        own_round1_statement=own_round1,
    )
```

---

## Chat WebSocket Integration

Duel reuses the **existing chat WebSocket** — no separate connection.

### Frontend → Backend

```json
{
  "type": "duel_start",
  "topic": "Should I change jobs this year?",
  "specialist_ids": ["career-strategist", "financial-planner"]
}
```

### Backend → Frontend (event stream)

```json
{"type": "duel_setup", "specialists": [...], "topic": "..."}
{"type": "duel_round_start", "round": 1, "label": "Opening Positions"}
{"type": "duel_specialist_start", "specialist": "Career Strategist", "round": 1}
{"type": "duel_specialist_delta", "specialist": "Career Strategist", "content": "...", "round": 1}
{"type": "duel_specialist_done", "specialist": "Career Strategist", "round": 1}
{"type": "duel_specialist_start", "specialist": "Financial Planner", "round": 1}
{"type": "duel_specialist_delta", "specialist": "Financial Planner", "content": "...", "round": 1}
{"type": "duel_specialist_done", "specialist": "Financial Planner", "round": 1}
{"type": "duel_round_start", "round": 2, "label": "Counter-Arguments"}
{"type": "duel_specialist_start", "specialist": "Career Strategist", "round": 2}
{"type": "duel_specialist_delta", "specialist": "Career Strategist", "content": "...", "round": 2}
{"type": "duel_specialist_done", "specialist": "Career Strategist", "round": 2}
{"type": "duel_specialist_start", "specialist": "Financial Planner", "round": 2}
{"type": "duel_specialist_delta", "specialist": "Financial Planner", "content": "...", "round": 2}
{"type": "duel_specialist_done", "specialist": "Financial Planner", "round": 2}
{"type": "duel_judge_start"}
{"type": "duel_judge_done", "scores": {...}, "winner": "...", "reasoning": "..."}
{"type": "duel_done", "saved_path": "decisions/2026-04-14-duel-should-i-change-jobs.md"}
```

### Backend: `routers/chat.py` changes

```python
# In the existing WS handler, add duel branch:
if data.get("type") == "duel_start":
    await _handle_duel(websocket, data, session_id, workspace_path)
    return

async def _handle_duel(websocket, data, session_id, workspace_path):
    config = DuelConfig(
        topic=data["topic"],
        specialist_ids=data["specialist_ids"],
    )
    orchestrator = DuelOrchestrator(claude_service)
    verdict_data = None
    async for event in orchestrator.run(config, workspace_path):
        payload = {
            "type": f"duel_{event.type}",
            "specialist": event.specialist,
            "content": event.content,
            "round": event.round_num,
        }
        if event.metadata:
            payload.update(event.metadata)
        await websocket.send_json(payload)

        if event.type == "judge_done":
            verdict_data = event.metadata

    # Add verdict summary to session so user can continue chatting
    if verdict_data:
        summary = (
            f"Duel: {data['topic']}\n"
            f"Winner: {verdict_data['winner']}\n"
            f"Reasoning: {verdict_data['reasoning']}\n"
            f"Recommendation: {verdict_data['recommendation']}"
        )
        session_service.add_message(session_id, "assistant", summary)
```

---

## Memory Save — Duel-Debate Type

### Frontmatter

```yaml
---
title: "Duel: Should I change jobs?"
type: duel-debate
date: 2026-04-14
specialists:
  - career-strategist
  - financial-planner
winner: financial-planner
scores:
  career-strategist: 18
  financial-planner: 22
tags:
  - career
  - decision
  - duel
---
```

### Body

```markdown
# Duel: Should I change jobs?

> ⚔️ Intellectual duel between 💼 Career Strategist and 💰 Financial Planner
> 2 rounds · 2026-04-14

## Round 1 — Opening Positions

### 💼 Career Strategist
[full Round 1 statement]

### 💰 Financial Planner
[full Round 1 statement]

## Round 2 — Counter-Arguments

### 💼 Career Strategist — Rebuttal
[full Round 2 statement]

### 💰 Financial Planner — Rebuttal
[full Round 2 statement]

---

## ⚖️ Verdict

### Score Bar
💼 Career Strategist: 18/25 (45%)
💰 Financial Planner: 22/25 (55%)

### Criteria Breakdown

| Criterion | 💼 Career | 💰 Finance |
|-----------|----------|-----------|
| Relevance | 4/5 | 4/5 |
| Evidence | 3/5 | 5/5 |
| Argument strength | 4/5 | 4/5 |
| Counter-argument | 3/5 | 4/5 |
| Actionability | 4/5 | 5/5 |
| **Total** | **18/25** | **22/25** |

### 🏆 Winner: Financial Planner

"Stronger evidence from your savings data, identified a real gap in the career
argument about timing assumptions, and provided a concrete 6-month action plan."

### Recommendation
[Jarvis's balanced recommendation]

### Action Items
- [ ] ...
- [ ] ...
- [ ] ...
```

### Save Location

```
memory/decisions/{date}-duel-{topic-slug}.md
```

### Graph Nodes and Edges

Step 15a auto-ingests the note → tags, people, links.

Additionally, `save_duel_to_memory` adds explicit edges:

```python
for spec_id in config.specialist_ids:
    graph_service.add_edge(
        f"note:decisions/{filename}",
        f"specialist:{spec_id}",
        "debated_by",
        weight=0.9,
    )
# Winner edge gets higher weight
graph_service.add_edge(
    f"note:decisions/{filename}",
    f"specialist:{verdict.winner}",
    "won_by",
    weight=1.0,
)
```

Council/duel nodes in the graph use **amber/gold color** to distinguish
from regular notes (blue) and people (green).

---

## Frontend Components

### `DuelSetup.vue`

Inline panel above chat input bar.

- Props: `specialists: SpecialistSummary[]`, `prefillTopic?: string`
- Emits: `start(config)`, `cancel`
- Logic: topic textarea, specialist checkboxes (exactly 2), cost estimate, start/cancel
- Validation: exactly 2 specialists selected, non-empty topic

### `DuelDebateView.vue`

Replaces ChatPanel message list while duel is active.

- Props: `topic, events: DuelEvent[], phase`
- Shows: round labels, specialist cards with streaming text, status indicators
- Auto-collapses Round 1 when Round 2 starts (expand on click)
- Phase: `round1 → round2 → judging → verdict`
- Cancel button stops duel mid-stream

### `DuelScoreBar.vue`

Score visualization component.

- Props: `scores: {[specialistId]: {criterion: score}}`, `specialists`, `winner`
- Shows: main score bar (percentage split), per-criterion breakdown bars
- Aesthetic: clean horizontal bars, specialist colors, subtle animation on reveal
- Winner badge: 🏆 icon with reasoning text below

```vue
<!-- Main score bar concept -->
<div class="duel-score-bar">
  <div class="bar-left" :style="{ width: percentA + '%' }">
    {{ specialistA.name }} · {{ totalA }}/25
  </div>
  <div class="bar-right" :style="{ width: percentB + '%' }">
    {{ totalB }}/25 · {{ specialistB.name }}
  </div>
</div>

<!-- Per-criterion breakdown -->
<div v-for="criterion in criteria" class="criterion-row">
  <span class="criterion-label">{{ criterion }}</span>
  <div class="criterion-bar-a" :style="barStyle(scores[specA][criterion], 5)" />
  <div class="criterion-bar-b" :style="barStyle(scores[specB][criterion], 5)" />
</div>
```

### `useDuel.ts`

```typescript
export function useDuel() {
  const isActive = useState<boolean>('duelActive', () => false)
  const topic = useState<string>('duelTopic', () => '')
  const events = useState<DuelEvent[]>('duelEvents', () => [])
  const phase = useState<string>('duelPhase', () => 'idle')
    // idle | setup | round1 | round2 | judging | verdict | done
  const verdict = useState<DuelVerdict | null>('duelVerdict', () => null)

  function start(config: DuelConfig) {
    isActive.value = true
    phase.value = 'round1'
    events.value = []
    verdict.value = null
    topic.value = config.topic
    sendWsMessage({ type: 'duel_start', ...config })
  }

  function handleWsEvent(event: any) {
    if (event.type === 'duel_round_start' && event.round === 2) phase.value = 'round2'
    if (event.type === 'duel_judge_start') phase.value = 'judging'
    if (event.type === 'duel_judge_done') {
      phase.value = 'verdict'
      verdict.value = {
        scores: event.scores,
        winner: event.winner,
        reasoning: event.reasoning,
        recommendation: event.recommendation,
        action_items: event.action_items,
      }
    }
    if (event.type === 'duel_done') {
      phase.value = 'done'
      setTimeout(() => { isActive.value = false }, 500)
    }
    events.value = [...events.value, event]
  }

  function cancel() {
    isActive.value = false
    phase.value = 'idle'
    events.value = []
    verdict.value = null
  }

  return { isActive, topic, events, phase, verdict, start, handleWsEvent, cancel }
}
```

### `main.vue` / `ChatPanel.vue` Integration

```vue
<template>
  <!-- Normal chat messages -->
  <ChatPanel v-if="!duel.isActive.value" ... />

  <!-- Duel debate view (replaces chat during duel) -->
  <DuelDebateView
    v-else
    :topic="duel.topic.value"
    :events="duel.events.value"
    :phase="duel.phase.value"
    :verdict="duel.verdict.value"
    @cancel="duel.cancel()"
  />

  <!-- Input bar — always visible, duel button added, disabled during duel -->
</template>
```

---

## Token Budget

| Component | Tokens (est.) |
|-----------|--------------|
| Specialist A Round 1 prompt (context + framing) | ~2500 |
| Specialist A Round 1 response | ~700 |
| Specialist B Round 1 prompt | ~2500 |
| Specialist B Round 1 response | ~700 |
| Specialist A Round 2 prompt (+ opponent's R1) | ~2000 |
| Specialist A Round 2 response | ~600 |
| Specialist B Round 2 prompt (+ opponent's R1) | ~2000 |
| Specialist B Round 2 response | ~600 |
| Judge prompt (topic + all 4 statements) | ~3500 |
| Judge response (JSON verdict) | ~500 |
| **Total** | **~15,600** |
| **Cost (Sonnet)** | **~$0.06** |

5 Claude API calls total (2 × Round 1 + 2 × Round 2 + 1 Judge).

---

## Acceptance Criteria

- [ ] ⚔️ button in chat input bar opens DuelSetup panel
- [ ] User selects topic + exactly 2 specialists, sees cost estimate
- [ ] On "Start Duel", chat transitions to DuelDebateView
- [ ] Round 1: each specialist streams opening position sequentially
- [ ] Round 2: each specialist streams counter-argument referencing opponent's R1
- [ ] Round 1 auto-collapses when Round 2 starts
- [ ] System prompts force argumentative engagement (not parallel monologues)
- [ ] After both rounds, Jarvis judges with 5 explicit criteria (1–5 each)
- [ ] Score bar shows relative strength as percentage split
- [ ] Per-criterion breakdown displayed below main bar
- [ ] Winner declared with specific reasoning referencing debate points
- [ ] Verdict includes recommendation + action items
- [ ] On completion, duel view fades, verdict appears as chat message
- [ ] User can continue chatting (verdict in session context)
- [ ] Result auto-saves to `memory/decisions/` with `type: duel-debate` frontmatter
- [ ] Graph updated: duel node + specialist edges + winner edge (via step 15a)
- [ ] Duel events flow through existing chat WebSocket (no separate WS)
- [ ] No tools during duel (pure reasoning)
- [ ] Total latency < 35s for full duel
- [ ] Cancellation works mid-duel
- [ ] Elegant "intellectual duel" aesthetic — not gamified arena
