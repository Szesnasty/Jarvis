---
title: Duel Mode
status: current
last_updated: 2026-04-15
depends_on: [chat, specialists, knowledge-graph]
---

# Duel Mode

## Summary

Duel Mode enables two specialists to debate a user-defined topic across two rounds (opening positions + counter-arguments), judged by an AI arbiter on 5 criteria. The verdict, scores, and recommendation are saved to memory and the knowledge graph.

## How It Works

### Backend (`council.py`)

The `DuelOrchestrator` runs a structured debate:

1. **Setup**: Validates config (exactly 2 specialists, non-empty topic), loads specialist configs, builds shared context via retrieval pipeline
2. **Round 1**: Each specialist generates an opening position (max 250 words) using their role, rules, and the shared context
3. **Round 2**: Each specialist generates a counter-argument (max 200 words) seeing the opponent's Round 1 text
4. **Judging**: A judge prompt scores both specialists on 5 criteria (relevance, evidence, argument_strength, counter_argument, actionability) on a 1–5 scale, producing structured JSON
5. **Memory Save**: The full debate is saved to `memory/decisions/{date}-duel-{slug}.md` with frontmatter, and graph edges (`debated_by`, `won_by`) are created

All Claude API calls use `ClaudeService.stream_response()` with empty tools list. Events are yielded as an async generator (`DuelEvent` dataclass).

### WebSocket Integration (`chat.py`)

A `duel_start` message type triggers `_handle_duel()` which:
- Creates a `DuelOrchestrator` and runs it
- Maps each `DuelEvent` to a WebSocket JSON message prefixed with `duel_`
- Event types: `duel_setup`, `duel_round_start`, `duel_specialist_delta`, `duel_specialist_done`, `duel_judge_start`, `duel_judge_done`, `duel_done`, `duel_error`

### Frontend

- **`useDuel.ts`**: State management composable with `isActive`, `topic`, `events`, `phase`, `verdict`, `currentTexts`. Routes WS events via `handleWsEvent()`.
- **`DuelSetup.vue`**: Inline panel with topic textarea, specialist checkboxes (exactly 2), cost/time estimate, session spend warning.
- **`DuelDebateView.vue`**: Live 2-round timeline with streaming text, specialist cards with pulsing dot, auto-collapse Round 1 during Round 2, judging indicator, and embedded `DuelScoreBar`.
- **`DuelScoreBar.vue`**: Main percentage bar + per-criterion breakdown (5 criteria), winner badge with reasoning.
- **Chat integration**: ⚔️ button in ChatPanel input bar, `/duel` command, duel view replaces chat during active duel, verdict appended as chat message on completion.

## Key Files

| File | Purpose |
|------|---------|
| `backend/services/council.py` | DuelOrchestrator, prompts, scoring, memory save |
| `backend/routers/chat.py` | WebSocket duel handler + event mapping |
| `backend/tests/test_duel_backend.py` | 13 tests for config, prompts, parsing, save |
| `frontend/app/composables/useDuel.ts` | Duel state management + WS routing |
| `frontend/app/components/DuelSetup.vue` | Setup panel UI |
| `frontend/app/components/DuelDebateView.vue` | Live debate timeline |
| `frontend/app/components/DuelScoreBar.vue` | Score visualization |

## API / Interface

### WebSocket Messages

**Client → Server:**
```json
{ "type": "duel_start", "topic": "...", "specialist_ids": ["id1", "id2"] }
```

**Server → Client events:**
- `duel_setup` — specialists metadata
- `duel_round_start` — `{ round: 1|2, label: "..." }`
- `duel_specialist_delta` — streaming text chunk `{ specialist, content, round }`
- `duel_specialist_done` — specialist finished for round
- `duel_judge_start` — judging phase begins
- `duel_judge_done` — `{ scores, winner, reasoning, recommendation, action_items }`
- `duel_done` — `{ saved_path, duel_id }`
- `duel_error` — `{ content }`

### Scoring Criteria

| Criterion | Description |
|-----------|-------------|
| relevance | How relevant is the argument to the user's topic and context? |
| evidence | Does the argument use concrete evidence from the user's notes? |
| argument_strength | How well-structured and logical is the reasoning? |
| counter_argument | How effectively does the specialist address the opponent's points? |
| actionability | Does the argument lead to clear, actionable recommendations? |

## Gotchas

- `DuelOrchestrator.run()` is an async generator — must be consumed with `async for`
- The judge sometimes returns non-JSON despite instructions — `parse_judge_verdict()` has fallback logic
- Token budget is capped at 25,000 total across all duel API calls
- Exactly 2 specialists required — validation enforced on both frontend and backend
