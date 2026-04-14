---
title: Chat & Claude Integration
status: active
type: feature
sources:
  - backend/routers/chat.py
  - backend/services/claude.py
  - backend/services/_anthropic_client.py
  - backend/services/tools.py
  - backend/services/token_tracking.py
  - frontend/app/composables/useChat.ts
  - frontend/app/composables/useWebSocket.ts
  - frontend/app/components/ChatPanel.vue
depends_on: [retrieval, sessions, specialists]
last_updated: 2026-04-14
---

# Chat & Claude Integration

## Summary

This is the core conversation loop of Jarvis: a WebSocket channel carries user messages to the backend, which retrieves relevant memory context, calls Claude (claude-sonnet-4-20250514) with streaming enabled, and forwards response tokens back to the browser in real time. Claude can also invoke tools during a response — reading or writing notes, querying the graph, creating plans — with the tool call chain completing before the browser finalises the message.

## How It Works

### Connection lifecycle

The frontend opens a single persistent WebSocket to `GET /api/chat/ws` on page load. The backend immediately creates a session and sends `session_start` with a `session_id`. That ID travels with every subsequent message so the backend appends to the correct conversation history. If the connection drops, `useWebSocket` schedules an exponential backoff reconnect (1 s → 2 s → 4 s → … capped at 15 s) and sends a synthetic `disconnected` event so the chat UI can reset its loading state without waiting.

A heartbeat ping is sent from the frontend every 25 seconds to keep the connection alive through proxies. The backend silently ignores `ping` frames.

### Per-message flow

For each user message the backend (`_handle_message` in `chat.py`) runs the following sequence:

1. **Context retrieval** — `build_system_prompt` calls `build_context` (from `context_builder`) to find relevant notes and appends them to the base system prompt. If a specialist is active, its prompt fragment is injected first.
2. **Tool filtering** — `specialist_service.filter_tools` narrows the full `TOOLS` list to those permitted by the active specialist (or all tools if none is active).
3. **First Claude stream** — `ClaudeService.stream_response` opens a streaming request to the Anthropic Messages API. `text_delta` events are forwarded to the WebSocket immediately as they arrive.
4. **Tool call handling** — If Claude emits a `tool_use` block, its JSON input is accumulated across streaming deltas by `_ToolAccumulator` and yielded as a single `StreamEvent` only when the `content_block_stop` event arrives. The router then executes the tool, appends both the assistant tool-use block and the tool result to the message list, and calls `_stream_follow_up` to get Claude's next response.
5. **Recursive tool rounds** — `_stream_follow_up` is recursive. Each recursive call increments a `depth` counter. The chain is cut off at `MAX_TOOL_ROUNDS = 5` to prevent runaway loops.
6. **Session save** — After every exchange the full session is persisted to disk (crash protection). On WebSocket disconnect the session is additionally written to `memory/` as a Markdown note.
7. **Token logging** — Accumulated `input_tokens` + `output_tokens` from all rounds in a turn are written to `app/logs/token_usage.jsonl` via `log_usage`.

### Error handling in ClaudeService

All Anthropic SDK exceptions are caught and converted to `StreamEvent(type="error")` with user-readable messages. Rate limits, 529 overload responses, 401 authentication failures, and generic 5xx errors each get distinct copy. The frontend detects whether an error message is retryable (matches "try again", "overloaded", "rate limit", or "reconnect") and shows a Retry button if so.

### Frontend state

`useChat` owns all conversation state: the message list, the streaming `currentResponse` buffer, loading/error flags, and `toolActivity` (a label like "Searching notes…" shown while a tool runs). It delegates connection management entirely to `useWebSocket`. When a `done` event arrives, `currentResponse` is flushed into the `messages` array and loading state clears.

`ChatPanel.vue` renders messages with `marked` + `DOMPurify` for safe Markdown output. The streaming response is rendered live with a blinking cursor appended. A URL detection feature watches the input field: if a URL is typed, a toolbar appears offering to save it to memory via `ingestUrl` (bypassing Claude entirely — this is a direct REST call to the ingest endpoint).

### Token budget constants

`token_tracking.py` defines soft budget caps intended for use in context assembly:

| Constant | Value |
|---|---|
| `TOTAL_BUDGET` | 4000 tokens |
| `CONTEXT_BUDGET` | 2500 tokens |
| `PREFERENCES_BUDGET` | 500 tokens |
| `SPECIALIST_BUDGET` | 500 tokens |
| `HISTORY_BUDGET` | 500 tokens |

These constants are defined and exported but are not currently enforced — `check_budget` is never called before Claude API calls. Token usage is logged at `$3/MTok` input and `$15/MTok` output (claude-sonnet-4 pricing at time of writing).

## Key Files

- `backend/routers/chat.py` — WebSocket endpoint, per-message orchestration, recursive tool chain loop, session save-on-disconnect
- `backend/services/claude.py` — `ClaudeService` wrapping the Anthropic streaming API; `_ToolAccumulator` for reassembling fragmented tool-input JSON; `build_system_prompt` for context injection
- `backend/services/_anthropic_client.py` — Sync `anthropic.Anthropic` factory, present for test-mocking intent but unused by the codebase (all live paths use `AsyncAnthropic` directly in `ClaudeService`)
- `backend/services/tools.py` — `TOOLS` list (Claude-facing schemas) and `execute_tool` dispatcher mapping tool names to service calls
- `backend/services/token_tracking.py` — Append-only JSONL usage log with per-day and all-time aggregation helpers; defines token budget constants (not yet enforced)
- `frontend/app/composables/useWebSocket.ts` — Persistent WebSocket with heartbeat, exponential-backoff reconnect, and multi-listener message dispatch
- `frontend/app/composables/useChat.ts` — Conversation state manager; maps raw WebSocket events to UI state; handles retry logic
- `frontend/app/components/ChatPanel.vue` — Message list, streaming cursor, typing indicator, tool activity label, error bar with retry, URL ingest toolbar

## API / Interface

### WebSocket protocol — `ws /api/chat/ws`

All frames are JSON. The client sends; the server sends back a stream of events until `done`.

**Client → Server**

```
// Start or resume a conversation turn
{ "type": "message", "content": string, "session_id"?: string }

// Keep-alive (silently ignored by server)
{ "type": "ping" }
```

`session_id` is optional on the first message. If omitted the server uses the session it created at connect time. Pass it on subsequent messages to keep the conversation continuous. Passing an unknown `session_id` is ignored — the server falls back to its own session.

**Server → Client**

```
{ "type": "session_start", "session_id": string }
// Sent immediately on connect, and again after each reconnect.

{ "type": "text_delta", "content": string }
// One or more per turn. Concatenate in order to form the full response.

{ "type": "tool_use", "name": string, "input": object }
// Claude is about to invoke a tool.

{ "type": "tool_result", "name": string, "content": string }
// Tool finished. Claude continues generating.

{ "type": "done", "session_id": string }
// Turn is complete. The final assembled response is already in session history.

{ "type": "error", "content": string }
// Recoverable or fatal error. Check content for user-facing message.
```

`disconnected` is a synthetic client-side-only event emitted by `useWebSocket` on socket close; it never comes from the server.

### Tool definitions

Tools are defined in `TOOLS` (`backend/services/tools.py`) as Anthropic-format input schemas and executed by `execute_tool`.

| Tool | Required inputs | What it does |
|---|---|---|
| `search_notes` | `query` | Keyword/tag search across the memory index; optional `folder` and `limit` |
| `read_note` | `path` | Reads full Markdown content of a note at `memory/{path}` |
| `write_note` | `path`, `content` | Creates or overwrites a note with full Markdown + frontmatter |
| `append_note` | `path`, `content` | Appends content to an existing note |
| `create_plan` | `title`, `items` | Generates a checklist Markdown note saved to `memory/plans/` |
| `update_plan` | `path`, `task_index`, `checked` | Toggles a checkbox in an existing plan |
| `summarize_context` | `content` | Saves a summary note to `memory/summaries/{date}-{slug}.md` |
| `save_preference` | `rule` | Persists a user behavior rule to `memory/preferences/` |
| `query_graph` | `entity` | Traverses the knowledge graph from an entity up to `depth` hops |
| `ingest_url` | `url` | Fetches a YouTube transcript or web article and saves it to memory |

All `path` values are relative to `memory/`. Tool errors are caught and returned as strings rather than exceptions, so Claude receives the error text and can decide how to respond.

### `useChat` composable interface

```typescript
const {
  messages,        // Ref<ChatMessage[]> — completed turns only
  currentResponse, // Ref<string> — streaming buffer, cleared on done
  isLoading,       // Ref<boolean>
  toolActivity,    // Ref<string> — e.g. "Searching notes..." or ""
  error,           // Ref<string> — auto-clears after 8 s
  canRetry,        // Ref<boolean> — true for transient errors
  sessionId,       // Ref<string>
  isConnected,     // Ref<boolean>
  init,            // () => void — call once on mount
  sendMessage,     // (content: string) => void
  retry,           // () => void — resends last message
  disconnect,      // () => void
} = useChat()
```

## Gotchas

**Tool input arrives fragmented.** The Anthropic streaming API sends tool input JSON as multiple `input_json_delta` events. `_ToolAccumulator` concatenates these strings and only parses the complete JSON on `content_block_stop`. If Claude sends malformed JSON for a tool input (rare but possible), the accumulator silently returns an empty dict `{}` rather than raising — so tools that require inputs may behave unexpectedly without a visible error.

**Only one tool call per Claude turn is handled.** The router tracks a single `pending_tool` variable per streaming pass. If Claude emits two `tool_use` blocks in the same response, only the last one is retained (each overwrites the previous). Any earlier tool calls in that pass are silently dropped. In current Anthropic API behaviour only one tool call is emitted per stop sequence, but this is a structural limitation with no guard.

**Session ID switching mid-connection.** A client can pass a different `session_id` in a message to resume a previous conversation. The server will switch context silently if that session exists. The frontend never does this intentionally today, but it means a replayed or forged frame could hijack session context.

**Token usage is logged per-turn, not per-streaming-event.** The `usage_acc` list accumulates tokens across all rounds (initial stream + all follow-up streams). A single conversational turn with three tool calls produces one log entry covering all four Claude API calls. This is intentional for cost tracking but means individual tool-call costs are not individually attributable.

**Error messages auto-clear after 8 seconds** in `useChat`. If the user does not notice and act (e.g. click Retry), the error disappears silently. The underlying WebSocket may still be reconnecting.

**URL ingest in ChatPanel bypasses Claude.** When the user types a URL and clicks "Save to memory", the `ingestUrl` REST call happens directly without going through the WebSocket or adding a user message to the history. The save result is shown in a transient status bar that disappears after 4 seconds and is not recorded in the session.

## Known Issues

### Critical

**Prompt injection via ingested note content** (`context_builder.py:52`). Raw note content — including pages fetched via `ingest_url` — is embedded verbatim into the system prompt with no sanitization. A web page or YouTube transcript that contains text resembling system instructions can manipulate Claude's behaviour for the remainder of the session.

### High

**Parallel tool calls are silently dropped** (`chat.py:96-97`, `chat.py:150-151`). Both `_handle_message` and `_stream_follow_up` track the current tool call in a single `pending_tool` variable. If the Anthropic API ever emits more than one `tool_use` block in a single streaming response (possible with future model versions or changed API behaviour), all but the last call are overwritten and never executed. There is no warning logged.

**`ClaudeService` instantiated per-message** (`chat.py:135`). `ClaudeService(api_key=api_key)` is called inside `_handle_message`, which runs on every WebSocket message. Each instantiation creates a new `anthropic.AsyncAnthropic` client and a new underlying HTTP connection pool. Under load this creates unnecessary connection churn. The service should be instantiated once per WebSocket connection or as a module-level singleton.

**Token budget constants are defined but never enforced** (`token_tracking.py:11-15`). `TOTAL_BUDGET`, `CONTEXT_BUDGET`, and related constants are exported from `token_tracking.py` but `check_budget` is never called before Claude API calls anywhere in the codebase. There is no mechanism to prevent runaway token consumption against the budget thresholds.

### Medium

**`_execute_summarize` performs synchronous file I/O on the async event loop** (`tools.py:313-339`). The `summarize_context` tool handler calls `target.write_text(...)` synchronously inside an `async` call chain. This blocks the event loop for the duration of the disk write. Additionally, it bypasses `memory_service.create_note`, meaning the saved summary is not indexed in SQLite, does not appear in search results, and has no path validation — Claude-supplied path components are used directly.

**Hard 500-character truncation in context assembly breaks mid-word** (`context_builder.py:52`). Notes are truncated to 500 characters without regard for word or sentence boundaries. This can produce cut-off words or broken Markdown at the context injection boundary, which may confuse Claude's reading of the injected note.

**`_anthropic_client.py` is dead code.** The module exports a `create_client` factory that returns a synchronous `anthropic.Anthropic` instance. The codebase uses `anthropic.AsyncAnthropic` directly in `ClaudeService.__init__` and `_anthropic_client.py` is never imported. It provides no live functionality and its presence implies a test-mocking path that does not exist.

### Frontend

**XSS via cursor `<span>` appended after DOMPurify** (`ChatPanel.vue:115`). The streaming response bubble is rendered as:

```
renderMarkdown(currentResponse) + '<span class=chat-panel__cursor>▊</span>'
```

`renderMarkdown` runs `DOMPurify.sanitize` on the Markdown output, but the cursor span is concatenated as a raw string after sanitization and set via `v-html`. If `currentResponse` ends with content that can break out of the sanitized HTML context before the append, the cursor span bypasses DOMPurify. The span should be injected via a DOM API or template ref rather than raw string concatenation.

**`URL_RE` matches trailing punctuation** (`ChatPanel.vue:37`). The regex `/https?:\/\/[^\s]+/` captures everything up to the next whitespace, including trailing punctuation like commas, periods, and closing parentheses. A sentence like "see https://example.com." will match `https://example.com.` (with the period), producing an invalid URL passed to the ingest endpoint.

**`_errorClearTimer` is never cleared on component unmount** (`useChat.ts:13`). The 8-second auto-clear timer is stored in `_errorClearTimer` but `useChat` has no `onUnmounted` hook. If the component is destroyed while a timer is pending, the callback fires against a stale ref, which in Vue 3 is harmless but still leaks the timer handle.

**Reconnect callbacks fire on first connection** (`useWebSocket.ts:26-43`). The reconnect guard checks `_reconnectAttempts > 0 || _ws.value !== ws`. On the very first `connect()` call, `_ws.value` is `null` and `ws` is the newly created socket, so `_ws.value !== ws` is always true and all registered `onReconnect` callbacks fire immediately. In `useChat`, this resets `sessionId` to an empty string on first connect, before `session_start` arrives. In practice this is harmless because `session_start` follows immediately, but any `onReconnect` handler that assumes a prior session existed will run incorrectly on cold start.

**`disconnected` event handled via `any` cast** (`useChat.ts:66`). The `_handleEvent` function receives a typed `WsEvent` but falls through to `(event as any).type === 'disconnected'` because `'disconnected'` is not in the `WsEvent` union. This bypasses TypeScript's exhaustiveness checking. The `WsEvent` type should be extended to include the synthetic `disconnected` event type.
