# Step 16b — Duel Mode: Frontend (UI, Score Bar, Chat Integration)

> **Goal**: Build the complete Duel frontend — setup panel, live debate view
> with 2-round streaming, score bar with per-criterion breakdown, winner
> declaration, and seamless chat integration.

**Status**: ⬜ Not started
**Depends on**: Step 16a (duel backend must be working, WS events streaming)

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `DuelSetup.vue` | Inline panel: topic input, 2-specialist picker, cost estimate |
| `DuelDebateView.vue` | Live 2-round timeline with streaming text |
| `DuelScoreBar.vue` | Main score bar + per-criterion breakdown + winner badge |
| `useDuel.ts` | State management + WS event routing |
| Chat integration | ⚔️ button, chat↔duel view toggling, verdict as chat message |

---

## File Structure

```
frontend/
  app/
    components/
      DuelSetup.vue         # Inline setup panel
      DuelDebateView.vue    # Live 2-round debate timeline
      DuelScoreBar.vue      # Criteria-based score visualization
    composables/
      useDuel.ts            # Duel state + WebSocket integration
```

No `pages/duel.vue`. Everything integrates into `main.vue` / `ChatPanel.vue`.

---

## UX Flow

### 1. Entry — ⚔️ Button in Chat Input Bar

```
┌─────────────────────────────────────┐
│  Talk to Jarvis...          🎤 ⚔️ ➤ │
└─────────────────────────────────────┘
```

Alternative entries:
- User types "/duel" → auto-opens setup
- If input has text, pre-fills topic

### 2. Setup — `DuelSetup.vue`

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

- Inline panel above chat input bar (slides up)
- Exactly 2 specialists required (validation)
- Non-empty topic required
- **Cost/complexity hint always visible** (not hidden in a tooltip):
  - `"2 rounds · 5 scoring criteria · ~$0.08 · ~30s"`
  - If user has spent > $1 on duels this session: show amber warning
    `"⚠️ You've spent ~$X.XX on duels today"`
- Cost estimate: `2 × 2 rounds × ~3000 tokens + judge ~2000`

### 3. During Duel — `DuelDebateView.vue`

Replaces ChatPanel while duel is active.

**Round 1:**
```
┌─────────────────────────────────────────┐
│  ⚔️ Duel — "Should I change jobs?"       │
│  Round 1 of 2 · Opening Positions        │
├─────────────────────────────────────────┤
│                                          │
│  💼 Career Strategist                    │
│  ┌──────────────────────────────────┐    │
│  │ Based on your notes about        │    │
│  │ dissatisfaction and Q2 market...  │    │
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

**Round 2:** Round 1 auto-collapses, counter-arguments stream.

```
┌─────────────────────────────────────────┐
│  ⚔️ Duel — "Should I change jobs?"       │
│  Round 2 of 2 · Counter-Arguments        │
├─────────────────────────────────────────┤
│                                          │
│  Round 1 (collapsed — click to expand)   │
│  ├ 💼 Career Strategist ✓               │
│  └ 💰 Financial Planner ✓               │
│                                          │
│  💼 Career Strategist — Rebuttal         │
│  ┌──────────────────────────────────┐    │
│  │ The Financial Planner raises a    │    │
│  │ fair point about runway, but...   │    │
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

### 4. Verdict — `DuelScoreBar.vue`

```
┌─────────────────────────────────────────┐
│  ⚔️ Verdict                              │
│                                          │
│  ┌──────────────────────────────────┐    │
│  │  💼 Career     42%  ░░░░████████  │    │
│  │  Strategist         ████████░░░░  │    │
│  │                          58%  💰  │    │
│  │                  Financial Planner│    │
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

Score bar shows **relative strength** (percentage split).

### 5. After Verdict — Fade Back to Chat

Duel view fades. Verdict appended as chat message. User continues normally.

---

## Components

### `DuelSetup.vue`

- **Props**: `specialists: SpecialistSummary[]`, `prefillTopic?: string`, `sessionDuelSpend?: number`
- **Emits**: `start(config: DuelConfig)`, `cancel`
- **Logic**:
  - Topic textarea (required)
  - Specialist checkboxes (exactly 2 — disable "Start" until 2 selected)
  - Cost estimate always visible: rounds, criteria, estimated cost, estimated time
  - Session spend warning if `sessionDuelSpend > 1.0`
  - Start/Cancel buttons

### `DuelDebateView.vue`

- **Props**: `topic: string`, `events: DuelEvent[]`, `phase: string`, `verdict: DuelVerdict | null`
- **Emits**: `cancel`
- **Logic**:
  - Round label header (updates with phase)
  - Specialist cards: pulsing dot while streaming, ✓ when done
  - Auto-collapse Round 1 when Round 2 starts (click to expand)
  - "Judging..." indicator with subtle animation
  - Embeds `DuelScoreBar` when verdict arrives
  - Cancel button stops duel mid-stream

### `DuelScoreBar.vue`

- **Props**: `scores: Record<string, Record<string, number>>`, `specialists: Specialist[]`, `winner: string`, `reasoning: string`
- **Logic**:
  - Main score bar: horizontal split by percentage
  - Per-criterion breakdown: 5 small bars side by side
  - Winner badge with 🏆 and reasoning text
  - Subtle reveal animation (bars grow from center)

```vue
<div class="duel-score-bar">
  <div class="bar-left" :style="{ width: percentA + '%' }">
    {{ specialistA.name }} · {{ totalA }}/25
  </div>
  <div class="bar-right" :style="{ width: percentB + '%' }">
    {{ totalB }}/25 · {{ specialistB.name }}
  </div>
</div>

<div v-for="criterion in criteria" class="criterion-row">
  <span class="criterion-label">{{ criterion }}</span>
  <div class="criterion-bar-a" :style="barStyle(scores[specA][criterion], 5)" />
  <div class="criterion-bar-b" :style="barStyle(scores[specB][criterion], 5)" />
</div>
```

---

## `useDuel.ts` Composable

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

---

## Chat Integration

### `main.vue` / `ChatPanel.vue`

```vue
<template>
  <ChatPanel v-if="!duel.isActive.value" ... />

  <DuelDebateView
    v-else
    :topic="duel.topic.value"
    :events="duel.events.value"
    :phase="duel.phase.value"
    :verdict="duel.verdict.value"
    @cancel="duel.cancel()"
  />

  <!-- Input bar with ⚔️ button, disabled during active duel -->
</template>
```

### WS event routing in `useChat.ts`

```typescript
if (data.type?.startsWith('duel_')) {
  duel.handleWsEvent(data)
  return  // don't process as normal chat message
}
```

---

## Design Aesthetic

**Intellectual duel, not arena combat.**

- Clean, minimal cards for specialist statements
- Subtle pulsing dot for active streaming (not flashy animation)
- Score bar: solid horizontal bars, not pie charts or radial gauges
- Winner badge: 🏆 with reasoning — not confetti or fireworks
- Color palette: specialist accent colors (from their config), amber/gold for verdict
- Typography: same as rest of Jarvis — no special "game" fonts

---

## Definition of Done

- [ ] ⚔️ button in chat input bar opens DuelSetup
- [ ] DuelSetup validates: non-empty topic, exactly 2 specialists
- [ ] **Cost/time estimate always visible** in setup panel (not optional, not hidden)
- [ ] Session spend warning shown when > $1 spent on duels
- [ ] "Start Duel" sends `duel_start` via existing WS
- [ ] DuelDebateView replaces ChatPanel during active duel
- [ ] Round 1: specialist cards stream text with pulsing indicator
- [ ] Round 2: Round 1 auto-collapses, counter-arguments stream
- [ ] Phase transitions: round1 → round2 → judging → verdict (visual updates)
- [ ] DuelScoreBar: main percentage bar + per-criterion breakdown
- [ ] Winner declared with 🏆 badge and reasoning text
- [ ] "Saved to memory" + "Graph updated" confirmation shown
- [ ] On completion, duel view fades, verdict appears as chat message
- [ ] User can continue chatting (verdict in context)
- [ ] Cancel button works mid-duel (any phase)
- [ ] Input bar disabled during active duel
- [ ] Elegant aesthetic — refined, not gamified
