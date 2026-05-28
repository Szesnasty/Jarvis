# Step 30 — Chat Memory & Conversation Quality

> **Goal**: Make Jarvis hold a **long, coherent conversation in the
> user's language** without losing earlier turns, switching to English,
> or hallucinating about notes it already read. Focus on the chat
> pipeline only — no retrieval/graph changes.

**Parent**: (new track — conversation quality)
**Status**: 🟡 Planned
**Depends on**: Step 05 (Claude integration), Step 09 (specialists),
Step 21 (multi-provider).

---

## Why

Field feedback after Step 29 shipped:

> "Po kilkunastu turach Jarvis zaczyna gadać po angielsku, gubi wątek
> sprzed paru wiadomości i czasem wymyśla treść notatek których wcześniej
> nie cytował."

Root-cause analysis on `feat/specialist-note-ownership` identified **six
defects** in the chat pipeline, in three independent failure modes:

| Failure | Defect | Where |
|---|---|---|
| **Language drift** (PL → EN mid-conversation) | (1) script-only language detector + (6) specialist examples in EN | `services/claude.py::_language_reminder`, `specialist_service::build_multi_specialist_prompt` |
| **Lost thread** after ~10 exchanges | (2) hard cap `MAX_HISTORY_MESSAGES = 20` with no summary + (3) frontend race on `session_history` | `session_service.py`, `useChat.ts` |
| **Hallucinated note content** in deep tool chains | (5) 600-char stale-tool-result compaction + (4) timestamp/model junk in API messages | `routers/chat.py::_compact_stale_tool_results`, `session_service::get_messages` |

This step fixes all six. Sub-step **30b** is intentionally larger and gets
its own design — a **rolling conversation summary** is the only durable
fix for long-form chat.

---

## Sub-steps

### 30a — Language detection: bezogonkowy polski + sticky language

**File**: `backend/services/claude.py`

Today `_language_reminder()` looks only at script (Cyrillic, Chinese, Polish
diacritics, …). User types `"co tam"`, `"powiedz mi wiecej"`, `"kim jest
adam"` → no `ąęśćż` → classified as English → `LANGUAGE REMINDER` forces
English reply. This dominates every other instruction (it's the last
thing in the prompt by design).

**Fix**:

1. Add a small **stop-word allowlist per language**, checked when no
   diacritics are present. Polish stop-words (no diacritics): `co`,
   `czy`, `jak`, `dlaczego`, `kiedy`, `gdzie`, `kto`, `dla`, `ale`,
   `tez`, `tak`, `nie`, `mam`, `bylo`, `bedzie`, `juz`, `przez`, `bez`,
   `nad`, `pod`, `przed`, `mnie`, `tobie`, `jego`, `jej`, `nasz`, `wasz`,
   `moze`, `musze`, `chce`, `wiem`, `mysle`, `widze`. Similarly for DE
   (`und`, `oder`, `aber`, `nicht`, `mit`, `auch`, `dass`, `weil`) and
   ES (`que`, `pero`, `como`, `cuando`, `donde`, `porque`, `tambien`).
2. **Sticky language across the session.** Pass last 3 user messages
   to the detector (signature `_language_reminder(user_message, recent:
   list[str] = ())`). If any earlier message had clear diacritics or
   stop-words for language X, **keep X** for short follow-ups (`"i co
   dalej?"`, `"a teraz?"`).
3. Tighten the English fallback: only fall back to English when the
   message is ≥3 tokens and **none** of the stop-word lists matched.
   For 1–2 token utterances (`"ok"`, `"tak"`, `"thanks"`), inherit
   from the session's sticky language.

**Acceptance**:

- `_language_reminder("co tam")` returns Polish reminder.
- `_language_reminder("a teraz?", recent=["Cześć, jak się masz?"])`
  returns Polish reminder.
- `_language_reminder("hello")` returns English reminder.
- Unit tests in `backend/tests/test_language_detection.py` cover
  diacritic-free Polish, German, Spanish, plus sticky inheritance from
  recent messages.

**Effort**: ~30 min.

---

### 30b — Rolling conversation summary (the big one)

**Files**: `backend/services/session_service.py`,
`backend/services/conversation_summary.py` (new),
`backend/routers/chat.py`.

#### Problem

`MAX_HISTORY_MESSAGES = 20` (~10 user+assistant turns) is a **hard
cliff**. Past that, the 21st turn loses everything from turn 1. No
summary, no soft fade — the messages just vanish from the prompt sent
to Claude. After ~15 minutes of chatting, Jarvis legitimately has no
idea what was discussed earlier.

Simply raising the cap is wrong:

- Claude Sonnet has the context, but **every turn re-sends the whole
  history** — quadratic token cost. A 50-turn chat at 500 tok/turn =
  ~25 k tokens **per request**.
- Local models (Ollama) have small context windows. They genuinely
  cannot fit 40 turns.
- LiteLLM-routed providers (OpenAI, Gemini) bill per input token —
  unbounded history = unbounded cost.

We need a **rolling summary**: as the window slides, oldest turns get
collapsed into a compact recap that lives at the top of the message
list.

#### Design — two-tier sliding window

```
┌────────────────────────────────────────────────────────────┐
│  system: <Jarvis prompt + retrieved context + lang>        │
├────────────────────────────────────────────────────────────┤
│  system: Conversation so far (older turns):                │  ← rolling summary
│    - User asked about Adam Nowak's deadline                │     (≤ 600 tokens)
│    - Jarvis confirmed Aug 15, found in projects/q3.md      │
│    - User asked to add reminder, Jarvis wrote inbox/2026… │
├────────────────────────────────────────────────────────────┤
│  user: <turn N-K>                                          │  ← recent window
│  assistant: <turn N-K>                                     │     (K = 16 messages
│  ...                                                       │      = 8 turns,
│  user: <turn N>  ← latest                                  │      always verbatim)
└────────────────────────────────────────────────────────────┘
```

**Rules**:

- `RECENT_WINDOW = 16` messages (8 user+assistant turns) — never
  summarised, always sent verbatim. The "working memory" of the chat.
- `SUMMARY_TOKEN_BUDGET = 600` tokens (≈2400 chars). Hard cap.
- Summary is **rebuilt incrementally**, not from scratch every turn.
  When a new turn arrives:
  1. If `len(messages) <= RECENT_WINDOW + 2`, do nothing — no summary
     needed yet.
  2. Otherwise, take the **oldest 2 messages** that fall outside the
     window and **fold them into the existing summary** using a cheap
     summarisation call (1 round-trip to the same provider, ~100 tok
     output).
  3. If the resulting summary > `SUMMARY_TOKEN_BUDGET`, trigger a
     **compaction pass** that rewrites the whole summary to fit.

This keeps marginal cost flat (~1 small call per turn after window
fills) and total prompt cost capped at `RECENT_WINDOW * avg_turn +
SUMMARY_BUDGET`.

#### Storage

Summary is part of the session:

```python
session = {
    "id": ...,
    "messages": [...],          # full history, untrimmed
    "summary": "",              # rolling summary text
    "summary_covers_up_to": 0,  # index of last message folded into summary
    "created_at": ...,
}
```

`session.messages` keeps **everything** (in-memory + on disk in
`app/sessions/{id}.json`). `MAX_HISTORY_MESSAGES` becomes a soft
**eviction threshold** for in-memory cache only (e.g. 200), not a hard
truncation. The disk file remains the source of truth.

#### What goes to the LLM

New helper `session_service.build_llm_messages(session_id) -> tuple[str,
list[dict]]` returns `(summary_block, recent_messages)`. Chat.py
prepends `summary_block` to the system prompt and passes only
`recent_messages` to `claude.stream_response`.

```python
async def build_llm_messages(
    session_id: str,
    *,
    api_key: str | None = None,
    summariser: Callable | None = None,
) -> tuple[str, list[dict]]:
    """Return (summary_text, recent_messages) for the next LLM call.

    Triggers an incremental summary fold if older turns now fall
    outside RECENT_WINDOW. Pure read otherwise.
    """
```

#### Summariser

New module `backend/services/conversation_summary.py`:

```python
SUMMARY_SYSTEM = """\
You maintain a rolling summary of a conversation between a user and
Jarvis (their AI assistant). Output ONLY the updated summary — no
preface, no explanation.

Rules:
- Write in the user's language (matches the existing summary).
- Bullet form, ≤ 10 bullets total.
- Keep concrete facts: names, decisions, dates, file paths,
  unresolved questions.
- Drop chit-chat, acknowledgements, retrieval mechanics.
- Stay under {budget} tokens.
"""

async def fold_messages_into_summary(
    existing_summary: str,
    new_messages: list[dict],
    *,
    provider: str,
    model: str,
    api_key: str,
    budget_tokens: int = 600,
) -> str:
    ...
```

- Uses the **same provider as the active chat** so a local-only user
  doesn't suddenly hit the cloud. Pass `provider`, `model`, `api_key`
  from chat.py.
- Hard timeout 8 s. On error/timeout, **return existing_summary
  unchanged** — never block the chat reply. Log a warning. Next turn
  retries with a fresh batch.
- Lives **outside** the request path (`asyncio.ensure_future` after
  scheduling the session save), so it doesn't add latency to the
  visible reply.

#### Cost guard

If `provider == "ollama"` or `summary disabled in settings`, skip the
LLM call and use a **mechanical fallback**: keep `summary` as a plain
list of `User asked: ...` / `Jarvis: ...` short labels truncated to
120 chars each, capped at 10 entries. Cheap, no API cost, still
preserves topics.

A new settings flag `chat.summary_enabled` (default `true` for cloud
providers, `false` for ollama) controls this.

#### Persistence

`save_session()` already writes the whole session JSON; just include
the new fields. `resume_session()` already restores `messages`;
restore `summary` and `summary_covers_up_to` too. Backward-compatible:
absent fields default to `""` and `0`.

#### Tests

- `test_conversation_summary_fold` — folds 4 messages into an empty
  summary, returns non-empty string under budget.
- `test_summary_keeps_recent_window` — 30-message session, verifies
  `build_llm_messages` returns 16-message recent window + non-empty
  summary.
- `test_summary_failure_is_silent` — summariser raises → existing
  summary is preserved, chat call still goes through.
- `test_summary_persists_across_resume` — save + reload session,
  summary survives.
- `test_summary_disabled_for_ollama` — ollama provider skips API and
  uses mechanical fallback.

**Acceptance**:

- A 30-turn manual session keeps coherent context: in turn 28 ask
  about something from turn 3 — Jarvis recalls it.
- Token usage logged in `app/logs/usage.jsonl` shows **flat
  per-request cost** after turn 10, not linear growth.
- Ollama sessions never call the summariser.

**Effort**: ~3-4 h (most of the step).

---

### 30c — Fix `session_history` race in frontend

**File**: `frontend/app/composables/useChat.ts`

Today:

```ts
if (event.type === 'session_history') {
  if (messages.value.length === 0 && Array.isArray(event.messages)) {
    messages.value = event.messages
  }
  return
}
```

If the user types before history lands (refresh + fast click,
reconnect mid-typing), the local user message bumps `messages.length`
to 1 and the server's restored history is **silently dropped**. UI
shows an empty conversation despite the backend remembering everything.

**Fix**: merge by `timestamp + role + content` deduplication:

```ts
if (event.type === 'session_history') {
  if (!Array.isArray(event.messages)) return
  const seen = new Set(
    messages.value.map(m => `${m.role}|${m.timestamp ?? ''}|${m.content.slice(0, 50)}`)
  )
  const merged = [...event.messages]
  for (const m of messages.value) {
    const key = `${m.role}|${m.timestamp ?? ''}|${m.content.slice(0, 50)}`
    if (!seen.has(key)) merged.push(m)
  }
  messages.value = merged
}
```

**Acceptance**:

- Vitest covering: empty UI + history → restored. Local user message +
  history → merged, no duplicates. Re-sent history (reconnect storm) →
  no duplicate messages.

**Effort**: ~15 min.

---

### 30d — Clean message payload sent to LLM

**File**: `backend/services/session_service.py`

`get_messages()` returns the raw stored dict including `timestamp`,
`model`, `provider`. Anthropic SDK silently ignores them; LiteLLM
sometimes warns; OpenAI strict mode rejects. Always wasted tokens.

**Fix**: add `get_messages_for_api(session_id) -> list[dict]` that
returns only `{role, content}`. Chat.py uses this; UI continues to use
`get_messages()` for display (timestamps matter there).

**Acceptance**:

- `test_get_messages_for_api_strips_metadata` confirms only `role` and
  `content` keys are present.
- Chat router uses the new helper everywhere it builds `messages` for
  the LLM.

**Effort**: ~10 min.

---

### 30e — Don't over-compact stale tool results

**File**: `backend/routers/chat.py`

`_STALE_TOOL_RESULT_CAP = 600` chars is too aggressive. `read_note`
returns 2–5 KB of structured content; 600 chars = head+tail snippet
that loses middle sections, which the model then **fabricates** to fill
the gap.

**Fix**:

1. Raise `_STALE_TOOL_RESULT_CAP` to **2000** chars (~500 tokens).
   Empirically this fits one full note section while staying ~75%
   cheaper than the full result.
2. **Never compact the last 2 tool results** (not just the last 1).
   Multi-tool chains commonly reference results from 1 and 2 hops back.
3. Add `# Step 30e: do not lower without re-running eval` comment to
   discourage future "optimisation" without measuring quality.

**Acceptance**:

- `test_compact_stale_keeps_last_two` — chain of 4 tool results, last 2
  intact, first 2 compacted to 2000 chars.
- Manual eval: ask Jarvis to compare two notes (forces 2 `read_note`
  calls). The second call's content remains accurate when Jarvis
  synthesises.

**Effort**: ~10 min.

---

### 30f — Specialist examples must not leak language

**File**: `backend/services/specialist_service.py`

`build_multi_specialist_prompt` injects up to 2 examples per specialist
verbatim. If specialists were created in English (typical for
defaults), every chat carries 2× `User: hello / Assistant: Hi there!`
fragments — strong bias for English replies even when the language
reminder says Polish.

**Fix**: wrap examples in an explicit illustrative-only marker:

```python
sections.append(
    f"\n## Example outputs for {specialist['name']} "
    f"(STYLE REFERENCE ONLY — adapt language and content to the current user message)\n"
    f"User: {ex['user']}\nAssistant: {ex['assistant']}"
)
```

Also: examples are only emitted when the specialist has them — already
true, but document in a comment that they are **style hints**, not
language anchors.

**Acceptance**:

- Existing specialist tests still pass (just stronger heading).
- New test `test_specialist_examples_marked_illustrative` asserts the
  marker phrase is present whenever examples are emitted.

**Effort**: ~10 min.

---

## Rollout

1. Land **30a, 30c, 30d, 30e, 30f** in one PR — small, isolated, easily
   verifiable. Target same branch (`fix/chat-memory`).
2. Land **30b** in a follow-up PR. It's bigger, touches session
   persistence, and benefits from a manual smoke test (30-turn
   conversation) before merge.

## Non-goals

- No retrieval / context-builder changes (Step 28 territory).
- No prompt rewrite (Step 09 / Jarvis self).
- No new UI for showing the summary to the user (could be a follow-up).
- No multi-session memory bridging — summary stays per-session.

## Definition of Done

- All 6 issues fixed and covered by tests.
- 30-turn manual conversation in Polish stays in Polish and references
  turn 1 correctly in turn 28.
- Token cost per request after turn 10 stays roughly flat (≤ 20%
  variance) instead of growing linearly.
- Ollama users see no new outbound calls.
- `docs/.registry.json` updated for `services/conversation_summary.py`
  and feature doc `docs/features/conversation-summary.md`.
