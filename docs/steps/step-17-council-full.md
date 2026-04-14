# Step 17 — Council Full: Multi-Specialist Debate with Learning

> **Goal**: Expand Duel Mode (step 16) to support 3–4 specialists with
> inter-round compression, richer scoring, and knowledge extraction.
> Same chat-integrated approach, but deeper and more nuanced.

**Status**: ⬜ Not started (future / v2)
**Depends on**: Step 16 (Duel Mode must be working first)

---

## What Changes from Duel Mode

| Aspect | Duel (Step 16) | Council Full (Step 17) |
|--------|---------------|----------------------|
| Specialists | Exactly 2 | 3–4 |
| Rounds | 2 (position + counter) | 2 (position + targeted counter) |
| Counter-arguments | Each rebuts the other | Each rebuts the ONE they most disagree with |
| Judge output | 5 criteria, winner, reasoning | Same 5 criteria + alliance map + tension map |
| Compression | None needed | Round 1 summaries compressed before Round 2 prompts |
| Learning extraction | Action items only | Action items + extracted principles + graph enrichment |
| Cost | ~$0.06 | ~$0.12–0.15 |

---

## Core Design

### Still a Chat Feature

Same principle as step 16: no separate page, no separate WebSocket.
The ⚔️ button opens setup, user picks 3–4 specialists instead of 2.

### Round 1 — Opening Positions (3–4 specialists)

Each specialist presents their position sequentially.
Same prompt structure as step 16 Round 1, but with multiple opponents listed.

```python
# Prompt adjustment for Council:
OPPONENT: {opponent_names_list}  # "Career Strategist, Personal Coach, Health Guide"
# Instead of single opponent
```

### Inter-Round Compression

With 3–4 specialists, Round 1 produces 750–1000 words total.
Feeding all of that into each Round 2 prompt would blow the token budget.

**Solution**: Compress each Round 1 statement to ~100 words before Round 2.

```python
async def compress_round1(statements: dict, topic: str) -> dict:
    """Compress each specialist's R1 to ~100 words for R2 context."""
    compressed = {}
    for spec_id, text in statements.items():
        # Use Claude with tiny prompt to summarize
        summary = await claude.complete(
            f"Summarize this debate position in under 100 words. "
            f"Keep the thesis, key arguments, and main risk flag:\n\n{text}"
        )
        compressed[spec_id] = summary
    return compressed
```

This adds 3–4 small API calls but keeps Round 2 prompts within budget.

### Round 2 — Targeted Counter-Arguments

With 3+ specialists, "rebut your opponent" doesn't work — there are multiple.

**Rule**: Each specialist must pick the **one opponent they most disagree with**
and focus their counter-argument on that specific position.

```python
COUNCIL_ROUND2_PROMPT = """You are {name}, continuing a council debate.

## Other Specialists' Positions (Round 1 summaries)

{all_compressed_r1_statements}

## Your Task — Round 2

1. Read all opponents' positions above
2. Pick the ONE you most disagree with
3. Name them explicitly: "I challenge {opponent_name} because..."
4. Explain why their argument is weak on this specific point
5. Explain why YOUR approach better serves the user
6. If any opponent made a genuinely strong point, acknowledge it

CONSTRAINTS:
- Max 200 words
- You MUST name which opponent you're challenging
- Focus on ONE opponent — don't spread across all
- This is your final statement — make your strongest case"""
```

This creates a natural **alliance/opposition structure** the judge can map.

### Verdict — Extended Judge Output

Same 5 criteria per specialist, but with additional analysis:

```json
{
  "scores": {
    "career-strategist": { ... },
    "financial-planner": { ... },
    "personal-coach": { ... }
  },
  "ranking": ["financial-planner", "personal-coach", "career-strategist"],
  "winner": "financial-planner",
  "reasoning": "...",
  "alliance_map": {
    "financial-planner": "personal-coach",
    "career-strategist": null
  },
  "tension_map": {
    "financial-planner vs career-strategist": "timing vs financial readiness",
    "personal-coach vs career-strategist": "emotional readiness vs market conditions"
  },
  "recommendation": "...",
  "action_items": ["...", "...", "..."],
  "extracted_principles": [
    "Financial decisions of this magnitude need a 6-month runway",
    "Career transitions work best when emotionally ready, not just market-timed"
  ]
}
```

**Alliance map**: Who agreed with whom (based on Round 2 targeting).
**Tension map**: The key disagreements between pairs.
**Extracted principles**: General lessons from the debate, saved to `memory/knowledge/`.

### Knowledge Extraction (Learning from Debates)

After saving the debate note, the system also:

1. **Saves principles** to `memory/knowledge/principles-from-councils.md`:
   ```markdown
   ## 2026-04-14 — Should I change jobs?
   - Financial decisions of this magnitude need a 6-month runway
   - Career transitions work best when emotionally ready
   ```

2. **Enriches graph** with principle nodes linked to the debate and topic tags.

This means Jarvis **learns from its own debates** — future retrievals can pull
principles extracted from past council discussions.

---

## UX Differences from Duel

### Setup Panel

```
┌─────────────────────────────────────────┐
│  ⚔️ Council Mode                         │
│                                          │
│  Topic:                                  │
│  ┌──────────────────────────────────┐    │
│  │ Should I change jobs this year?  │    │
│  └──────────────────────────────────┘    │
│                                          │
│  Pick 3–4 specialists:                   │
│  [✓] 💼 Career Strategist               │
│  [✓] 💰 Financial Planner               │
│  [✓] 🧠 Personal Coach                  │
│  [ ] 🏋️ Health Guide                     │
│                                          │
│  2 rounds · 5 criteria · alliance map    │
│  ~$0.12 · ~45s                           │
│                                          │
│  [Start Council]  [Cancel]               │
└─────────────────────────────────────────┘
```

### Verdict View — Extended

Same DuelScoreBar but with 3–4 columns instead of 2.
Plus additional sections:

```
┌─────────────────────────────────────────┐
│  ⚔️ Council Verdict                      │
│                                          │
│  Score Ranking:                          │
│  🥇 💰 Financial Planner    21/25        │
│  🥈 🧠 Personal Coach       19/25        │
│  🥉 💼 Career Strategist    16/25        │
│                                          │
│  Alliance Map:                           │
│  💰 ↔ 🧠 (agreed on emotional readiness) │
│  💼 stood alone (market timing focus)    │
│                                          │
│  Key Tensions:                           │
│  💰 vs 💼: timing vs financial readiness │
│  🧠 vs 💼: emotional vs market factors   │
│                                          │
│  🏆 Winner: Financial Planner            │
│  "..."                                   │
│                                          │
│  📝 Saved to memory · 🔗 Graph updated   │
│  💡 2 principles extracted                │
└─────────────────────────────────────────┘
```

---

## Token Budget (3 specialists)

| Component | Tokens (est.) |
|-----------|--------------|
| 3 × Round 1 prompts | ~7500 |
| 3 × Round 1 responses | ~2100 |
| 3 × Compression calls | ~1500 |
| 3 × Round 2 prompts | ~6000 |
| 3 × Round 2 responses | ~1800 |
| Judge prompt (all statements) | ~4500 |
| Judge response (extended JSON) | ~800 |
| Principles extraction | ~500 |
| **Total** | **~24,700** |
| **Cost (Sonnet)** | **~$0.12** |

11 Claude API calls total.
With 4 specialists: ~$0.15, 14 calls.

---

## Implementation Priority

This step is **future / v2**. It should only be built after:
1. Step 16 (Duel Mode) is fully working and tested
2. Users have used Duel Mode enough to validate the concept
3. There's demand for richer multi-perspective analysis

The architecture of step 16 is designed to extend naturally:
- `DuelOrchestrator` → `CouncilOrchestrator` (subclass or mode flag)
- `DuelScoreBar` → supports N specialists via props
- `useDuel.ts` → `useCouncil.ts` wraps `useDuel` with extended state
- WebSocket events: same `duel_*` prefix, just more specialists

---

## Acceptance Criteria

- [ ] Setup allows selecting 3–4 specialists
- [ ] Round 1: all specialists stream positions sequentially
- [ ] Inter-round compression: R1 statements summarized before R2
- [ ] Round 2: each specialist explicitly names and challenges ONE opponent
- [ ] Judge scores all specialists on 5 criteria
- [ ] Ranking displayed (1st, 2nd, 3rd, optionally 4th)
- [ ] Alliance map shows who agreed with whom
- [ ] Tension map shows key disagreements between pairs
- [ ] Winner declared with specific reasoning
- [ ] Principles extracted and saved to `memory/knowledge/`
- [ ] Graph enriched with principle nodes + debate edges
- [ ] Total latency < 50s for 3 specialists
- [ ] Graceful degradation: if one specialist fails, debate continues with remaining
- [ ] Cost estimate accurate in setup panel
- [ ] Reuses step 16 infrastructure (same WS, same components extended)
