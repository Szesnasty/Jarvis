# Step 05 — Claude API Integration + Streaming + Tools

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 04 — Memory Service](step-04-memory-service.md) | **Next**: [Step 06 — Voice](step-06-voice.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

User types a message, Jarvis responds via Claude API with streaming. Claude can use tools to search/read/write notes. This is the core conversational loop.

---

## Files to Create / Modify

### Backend
```
backend/
├── routers/
│   └── chat.py                # NEW — chat endpoint (WebSocket)
├── services/
│   ├── claude.py              # NEW — Claude API wrapper
│   ├── context_builder.py     # NEW — build minimal context for Claude
│   ├── session_service.py     # NEW — manage session history
│   └── tools.py               # NEW — tool definitions + execution
└── models/
    └── schemas.py             # MODIFY — add chat schemas
```

### Frontend
```
frontend/src/
├── components/
│   └── ChatPanel.vue          # NEW — message list + streaming display
├── composables/
│   ├── useChat.ts             # NEW — chat logic
│   └── useWebSocket.ts        # NEW — WebSocket connection
├── stores/
│   └── chat.ts                # NEW — chat state store
├── views/
│   └── MainView.vue           # MODIFY — wire ChatPanel + text input
├── services/
│   └── api.ts                 # MODIFY — add WebSocket helpers
└── types/
    └── index.ts               # MODIFY — add ChatMessage types
```

---

## Specification

### System Prompt

```
You are Jarvis, a personal memory and planning assistant.

You work on the user's local knowledge base — Markdown files organized in folders.
The user's memory belongs to them. You help organize, search, plan, and connect their notes.

Rules:
- Be concise and direct
- Use the user's own notes as primary source
- When you create or modify notes, use Markdown with YAML frontmatter
- If you don't know something, say so — don't invent information
- When relevant, suggest saving important information to memory

You have access to the following tools to work with the user's memory.
```

### Claude Service (`services/claude.py`)

```python
class ClaudeService:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
    ) -> AsyncIterator[StreamEvent]:
        """Yields streaming events from Claude."""
        ...
```

- Uses `anthropic` async client
- Retrieves API key from keyring via `workspace_service.get_api_key()`
- Model: `claude-sonnet-4-20250514` (most recent Sonnet — best cost/quality for conversational use)
- `max_tokens`: 4096
- Streams response chunks

### Tool Definitions (`services/tools.py`)

MVP tools as Claude tool_use format:

```python
TOOLS = [
    {
        "name": "search_notes",
        "description": "Search the user's notes by keyword, tag, or topic. Returns matching note metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "folder": {"type": "string", "description": "Optional folder filter"},
                "limit": {"type": "integer", "description": "Max results", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_note",
        "description": "Read the full content of a specific note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path relative to memory/"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_note",
        "description": "Create or overwrite a note with Markdown content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path relative to memory/"},
                "content": {"type": "string", "description": "Full Markdown content with frontmatter"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "append_note",
        "description": "Append content to an existing note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path"},
                "content": {"type": "string", "description": "Content to append"}
            },
            "required": ["path", "content"]
        }
    }
]
```

### Tool Execution Loop

When Claude returns a `tool_use` block:
1. Parse tool name and input
2. Execute locally via `tools.py` dispatcher
3. Send tool result back to Claude
4. Continue streaming

```python
async def execute_tool(name: str, input: dict) -> str:
    match name:
        case "search_notes":
            results = await memory_service.search_notes(**input)
            return json.dumps([r.model_dump() for r in results])
        case "read_note":
            note = await memory_service.get_note(input["path"])
            return note.content
        case "write_note":
            await memory_service.write_note(input["path"], input["content"])
            return f"Note saved: {input['path']}"
        case "append_note":
            await memory_service.append_note(input["path"], input["content"])
            return f"Content appended to: {input['path']}"
        case _:
            return f"Unknown tool: {name}"
```

### Context Builder (`services/context_builder.py`)

Before sending to Claude, assemble context:

```python
async def build_context(user_message: str) -> str:
    """Build a small context string from relevant notes."""
    # 1. Search notes matching user message
    results = await memory_service.search_notes(user_message, limit=5)
    # 2. Read top results (truncated)
    context_parts = []
    for result in results[:3]:
        note = await memory_service.get_note(result.path)
        truncated = note.content[:500]
        context_parts.append(f"[{result.path}]\n{truncated}")
    # 3. Join with separator
    return "\n---\n".join(context_parts)
```

This context is prepended to the system prompt:
```
Here are potentially relevant notes from the user's memory:
{context}
```

**Token budget**: Keep total context under ~2000 tokens. This is MVP — graph-enhanced retrieval comes later.

### Session Service (`services/session_service.py`)

- Maintains in-memory conversation history per session
- Trims history to last 20 messages to control token usage
- Saves full session to `app/sessions/{session_id}.json` on session close

### WebSocket Chat Endpoint

```
WebSocket /api/chat/ws
```

Message format (client → server):
```json
{
  "type": "message",
  "content": "What did I plan for this week?",
  "session_id": "optional-session-id"
}
```

Message format (server → client):
```json
{"type": "text_delta", "content": "Based on your notes..."}
{"type": "tool_use", "name": "search_notes", "input": {"query": "week plan"}}
{"type": "tool_result", "name": "search_notes", "content": "[...]"}
{"type": "text_delta", "content": "I found your weekly plan..."}
{"type": "done", "session_id": "abc123"}
```

---

### Frontend

#### `ChatPanel.vue`

- Displays list of messages (user + assistant)
- Assistant messages stream in character by character
- Tool usage shown as collapsible activity indicator: "🔍 Searching notes..."
- Scrolls to bottom on new content

#### `useChat.ts` Composable

- Connects to WebSocket
- Sends user messages
- Accumulates streaming deltas into current assistant message
- Tracks tool execution state
- Exposes: `messages`, `isLoading`, `sendMessage()`

#### `useWebSocket.ts` Composable

- Manages WebSocket lifecycle (connect, reconnect, close)
- Heartbeat/ping to keep alive
- Exposes: `send()`, `onMessage()`, `isConnected`

#### `MainView.vue` Update

- Wire text input to `sendMessage()`
- Show `ChatPanel` between Orb and input
- Orb state: `idle` → `thinking` while Claude is responding

---

## Key Decisions

- WebSocket for streaming (not SSE) — bidirectional, good for tool loops
- Context builder adds ~3 most relevant notes, trimmed to 500 chars each
- Session history capped at 20 messages — prevents token explosion
- Model: `claude-sonnet-4-20250514` — good quality, reasonable cost
- Tool execution is synchronous within the response loop — no background jobs

---

## Acceptance Criteria

- [ ] User types message → sees streaming response from Claude
- [ ] Claude can search notes and reference them in response
- [ ] Claude can create a new note via write_note tool
- [ ] Tool execution visible in UI as activity indicator
- [ ] Orb shows `thinking` state during response
- [ ] Session history maintained across messages in same session
- [ ] No API key exposed in any API response or WebSocket message

---

## Tests

### Backend — `tests/test_claude_service.py` (~14 tests)
- `test_build_system_prompt_has_persona` → system prompt contains Jarvis persona
- `test_build_system_prompt_includes_preferences` → user prefs injected when present
- `test_build_system_prompt_includes_context` → relevant notes included when found
- `test_build_system_prompt_max_length` → prompt stays within token budget
- `test_build_messages_format` → messages match Anthropic API `{role, content}` format
- `test_build_messages_preserves_order` → chronological order maintained
- `test_tool_definitions_include_search` → `search_notes` in tools list
- `test_tool_definitions_include_write` → `write_note` in tools list
- `test_tool_definitions_schema_valid` → each tool has name, description, input_schema
- `test_execute_tool_search` → `search_notes` calls memory service, returns results
- `test_execute_tool_write` → `write_note` creates note via memory service
- `test_execute_unknown_tool` → unknown tool name → ToolNotFoundError
- `test_no_api_key_in_response_body` → response never contains raw API key
- `test_no_api_key_in_error_messages` → errors don't leak key

### Backend — `tests/test_chat_ws.py` (~10 tests)
- `test_ws_connect_succeeds` → WebSocket handshake 101
- `test_ws_connect_returns_session_id` → first message has session_id
- `test_ws_send_message_receives_chunks` → streaming text_delta events
- `test_ws_chunks_form_complete_response` → concatenated chunks = full response
- `test_ws_tool_use_event` → receives `tool_use` event with tool name + input
- `test_ws_tool_result_event` → `tool_result` follows `tool_use`
- `test_ws_session_history_grows` → 2nd message includes 1st in history
- `test_ws_invalid_json` → returns error event, connection stays open
- `test_ws_empty_message` → returns validation error event
- `test_ws_disconnect_cleanup` → session resources freed after disconnect

### Backend — `tests/test_chat_security.py` (~5 tests)
- `test_api_key_not_in_ws_messages` → scan all WS frames for key string
- `test_api_key_not_in_rest_responses` → scan all REST endpoint responses
- `test_prompt_injection_basic` → "ignore previous instructions" doesn't leak system prompt
- `test_tool_results_sanitized` → tool output doesn't contain raw paths outside workspace
- `test_rate_limit_handling` → Claude 429 → graceful error event to client

### Frontend — `tests/composables/useChat.test.ts` (~10 tests)
- `sendMessage()` connects WebSocket with correct URL
- `sendMessage()` sends JSON with `content` field
- Streaming chunks update `currentResponse` ref progressively
- `currentResponse` cleared when new message sent
- `isLoading` is true during streaming, false after
- Tool use event updates `toolActivity` ref
- Tool result clears `toolActivity`
- Session `messages` array grows after each exchange
- Error event sets `error` ref with message
- Disconnect during stream sets `error` + `isLoading = false`

### Frontend — `tests/components/ChatPanel.test.ts` (~7 tests)
- Renders message list from chat state
- User messages aligned right
- Assistant messages aligned left
- Streaming response shows typing indicator
- Tool activity shows "Searching notes..." or similar
- Text input at bottom with send button
- Send button disabled while loading

### Regression suite
```bash
cd backend && python -m pytest tests/ -v           # ALL backend tests
cd frontend && npx vitest run                       # ALL frontend tests
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~96 backend tests
cd frontend && npx vitest run                      # ~60 frontend tests
```

**Expected total: ~156 tests**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all ~96 backend tests pass (including regression)
- [ ] `npx vitest run` — all ~60 frontend tests pass (including regression)
- [ ] Manual: type message → streaming response visible
- [ ] No API key in any WS message or REST response (verified by security tests)
- [ ] Committed with message `feat: step-05 claude integration + streaming`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
