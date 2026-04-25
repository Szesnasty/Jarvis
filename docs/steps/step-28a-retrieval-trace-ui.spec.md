# Step 28a — Retrieval Trace UI

> **Goal**: After every Jarvis answer the user can open a panel that
> lists which notes fed the context, why each one was selected, and
> what its dominant signal was. Plumbing already exists; this step
> only surfaces it.

**Parent**: [step-28-document-intelligence.md](step-28-document-intelligence.md)
**Status**: ⬜ Planned

---

## Why

[pipeline.py:797-815](../../backend/services/retrieval/pipeline.py#L797-L815)
already attaches a `_signals` dict to every retrieved candidate. The
context builder at
[context_builder.py:562-565](../../backend/services/context_builder.py#L562-L565)
already tags graph-expansion notes with `via=` and `tier=` attributes
in the prompt sent to Claude. The user sees none of it. That makes
every quality decision (Step 28d, 28e, future re-weighting) a guess.

---

## Design

### What "trace" contains

For each note that ended up in the prompt:

```json
{
  "path": "knowledge/hai-ai-index/03-research-and-development.md",
  "title": "Research and Development",
  "score": 0.74,
  "reason": "primary",                // primary | expansion
  "via": "embedding",                 // bm25 | embedding | graph | expansion
  "edge_type": null,                  // present when reason=expansion
  "tier": null,                       // strong | weak when via=graph
  "signals": {
    "bm25": 0.42, "cosine": 0.81,
    "graph": 0.30, "boost": 0.0
  }
}
```

For graph-expansion notes:

```json
{
  "path": "client-rfp/access-control.md",
  "title": "Access Control",
  "score": 0.58,
  "reason": "expansion",
  "via": "graph",
  "edge_type": "related",
  "tier": "strong",
  "signals": {}
}
```

### Where it gets assembled

In [context_builder.py](../../backend/services/context_builder.py),
extend the existing `build_context(...)` (or its callsites in
`routers/chat.py`) to return a tuple `(prompt_str, trace_list)`
instead of just the prompt string. `trace_list` is the list above.

The hot loop already has the data — `_signals` per primary candidate,
and the `etype`/`tier`/`score` triple inside the expansion loop at
[context_builder.py:546-566](../../backend/services/context_builder.py#L546-L566).
This step simply collects them instead of dropping them after a debug
log line.

### Wire-through to the WebSocket

`/chat/ws` in [chat.py:527-528](../../backend/routers/chat.py#L527-L528)
streams Claude tokens. After the final `done` event, emit one new
event:

```json
{ "type": "trace", "items": [ ... ] }
```

(Order: `delta` … `delta` → `trace` → `done`. The frontend already
handles unknown event types as no-ops, so older clients degrade
without errors.)

### Frontend

In [ChatPanel.vue](../../frontend/app/components/ChatPanel.vue), each
assistant message gains an optional `trace?: TraceItem[]` field on
the message object. Render a small chevron `▸ Used context (N)` under
the message. Click expands to a list:

```
▾ Used context (4)
  ● knowledge/hai-ai-index/03-research-and-development.md   primary, embedding 0.81
  ● knowledge/hai-ai-index/05-policy.md                     primary, bm25 0.71
  ◌ client-rfp/access-control.md                            via related (strong)
  ◌ projects/jarvis-development.md                          via similar_to
```

Filled dot = primary hit, hollow dot = graph expansion. Clicking a
row navigates to `/memory?path=<path>` (existing route — see
[memory.vue:80](../../frontend/app/pages/memory.vue#L80)).

### Privacy / token cost

Trace items are paths + scores, not content. They add ~50 tokens to
the WS message but never to the Claude prompt itself, so this is
free at LLM cost.

---

## Code changes

| File | Change |
|------|--------|
| [backend/services/context_builder.py](../../backend/services/context_builder.py) | Refactor `build_context` and `build_graph_scoped_context` to return `(prompt, trace)`. Trace is built inline next to the existing debug logs. |
| [backend/routers/chat.py](../../backend/routers/chat.py) | After streaming completes, emit `{type: "trace", items}` over the WS. |
| [frontend/app/types/index.ts](../../frontend/app/types/index.ts) | Add `TraceItem` interface and `trace?: TraceItem[]` on the chat message type. |
| [frontend/app/composables/useChat.ts](../../frontend/app/composables/useChat.ts) | Handle `trace` event, attach `items` to the most recent assistant message. |
| [frontend/app/components/ChatPanel.vue](../../frontend/app/components/ChatPanel.vue) | New `<TraceList>` child component, collapsed by default. |

No new endpoints, no schema changes.

---

## Tests

- `backend/tests/test_context_builder_trace.py`:
  1. `test_trace_contains_primary_candidates` — synthetic candidates
     with known `_signals` produce a trace list matching them 1:1.
  2. `test_trace_distinguishes_expansion_from_primary` — graph
     expansion entries carry `reason=expansion` and `edge_type`.
  3. `test_trace_omits_dropped_candidates` — candidates that exceed
     the token budget are not in the trace (only what was *actually*
     sent).
- `backend/tests/test_chat_ws.py` (extend): assert that a `trace`
  event is emitted before `done` when context is non-empty.
- `frontend/test/components/ChatPanel.test.ts` (new or extend): render
  a message with a 3-item trace, assert collapsed by default, expand
  on click, assert navigation prop on row click.

---

## Acceptance

- Asking *"what does this RFP say about access control?"* produces a
  trace with at least 1 primary and 1 expansion entry, all paths
  resolving to existing notes in the workspace.
- The trace event arrives within the same WS stream as the answer —
  no extra HTTP round-trip.
- Toggling the panel does not reflow the chat history (fixed-height
  collapsed state).

---

## Out of scope

- Editing fusion weights from the UI.
- Persisting trace history (page refresh ⇒ traces gone, by design).
- Showing a trace for tool calls — only for retrieval-driven answers.
