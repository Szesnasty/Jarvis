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
6. **Session save** — `add_message` auto-persists after each append (crash protection). If Claude responds with text, the assistant message triggers another auto-save. If Claude returns only tool calls with no text, no redundant save is triggered since the user message already persisted. On WebSocket disconnect the session is additionally written to `memory/` as a Markdown note.
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

`check_budget()` is now called in `chat.py` before each Claude API call. When the accumulated token count exceeds `TOTAL_BUDGET`, the call is blocked and an error event is sent to the client. When the count exceeds the warning threshold, a notification event is sent but the call proceeds. Token usage is logged at `$3/MTok` input and `$15/MTok` output (claude-sonnet-4 pricing at time of writing).

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

`disconnected` is a synthetic client-side-only event emitted by `useWebSocket` on socket close; it never comes from the server. It is included in the `WsEvent` union type as `WsDisconnected`.

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

**Multiple tool calls per Claude turn are now handled.** The router accumulates all `tool_use` blocks from a single streaming pass into a list and executes each one in order before calling the follow-up stream. This removed the earlier limitation where only the last tool call in a pass was processed.

**Session ID switching mid-connection.** A client can pass a different `session_id` in a message to resume a previous conversation. The server will switch context silently if that session exists. The frontend never does this intentionally today, but it means a replayed or forged frame could hijack session context.

**Token usage is logged per-turn, not per-streaming-event.** The `usage_acc` list accumulates tokens across all rounds (initial stream + all follow-up streams). A single conversational turn with three tool calls produces one log entry covering all four Claude API calls. This is intentional for cost tracking but means individual tool-call costs are not individually attributable.

**Error messages auto-clear after 8 seconds** in `useChat`. If the user does not notice and act (e.g. click Retry), the error disappears silently. The underlying WebSocket may still be reconnecting.

**URL ingest in ChatPanel bypasses Claude.** When the user types a URL and clicks "Save to memory", the `ingestUrl` REST call happens directly without going through the WebSocket or adding a user message to the history. The save result is shown in a transient status bar that disappears after 4 seconds and is not recorded in the session.
