---
title: Session Management
status: active
type: feature
sources:
  - backend/routers/sessions.py
  - backend/services/session_service.py
  - frontend/app/composables/useSessions.ts
  - frontend/app/components/SessionHistory.vue
depends_on: [database, memory, knowledge-graph]
last_reviewed: 2026-04-14
last_updated: 2026-04-14
---

# Session Management

## Summary

Sessions are the unit of a single conversation with Jarvis. Each session tracks the message history, which tools were called, and which memory notes were touched. When a session ends, it can be persisted both as a JSON file for later resumption and as a Markdown note in `memory/conversations/` so the conversation becomes part of the searchable knowledge base.

## How It Works

### In-memory store and lifecycle

Active sessions live in a module-level dict (`_sessions`) in `session_service.py`. This is a deliberate simplicity choice for MVP: no database round-trips during an active conversation. A session is created with a 12-character hex UUID, starts with an empty message list, and tracks two sets: `tools_used` and `notes_accessed`. The `tools_used` set is initialized at creation; `notes_accessed` is initialized lazily via `setdefault` on first access. Both sets accumulate passively as the chat service calls `record_tool_use` and `record_note_access` during tool execution.

Message history is trimmed to the most recent 20 messages (`MAX_HISTORY_MESSAGES`) on every append, keeping the in-memory footprint bounded and preventing unbounded growth in long conversations. `add_message` now automatically calls `save_session` after each append so that the most recent message is persisted to disk immediately rather than only on explicit save calls.

### Persistence to disk (JSON)

`save_session` writes the active session to `{workspace}/app/sessions/{session_id}.json`. Sessions with fewer than 2 messages (no complete user+assistant exchange) are silently skipped — this prevents trivial "hi" sessions from cluttering the history list. The title stored in the JSON file is the first 100 characters of the first user message (raw truncation, no ellipsis).

`list_sessions` is an async function that offloads file I/O to a thread via `asyncio.to_thread` to avoid blocking the event loop. Files in the sessions directory are sorted by modification time (newest first) at the OS level, and scanning stops once `limit` entries have been collected, making the common case of fetching recent sessions an early-exit O(limit) scan rather than O(n). Trivial sessions (fewer than 2 messages) are filtered out during listing. Corrupt or unreadable files are skipped individually rather than failing the entire list.

### Resume flow

`resume_session` rehydrates a persisted session back into the in-memory store by reading its JSON file. The session ID stays the same, so the caller can resume sending messages as if the conversation never ended. The `tools_used` and `notes_accessed` fields are converted back from lists (JSON) to sets (Python) on load.

### Delete flow

Deletion is three steps, all called from the router: `delete_session` removes the in-memory entry, `delete_session_file` removes the JSON file from disk, and `graph_service.invalidate_cache()` is called so the knowledge graph rebuilds without stale session-derived data on next access. If the session was never saved (e.g., empty), `delete_session_file` is a no-op. The delete endpoint catches `SessionNotFoundError` and returns a 404 for invalid or non-existent session IDs.

### Conversation-to-memory pipeline

`save_session_to_memory` is the more significant write path. It converts a completed session into a Markdown note at `memory/conversations/{date}-{time}-{slug}.md`. This is what makes conversations searchable alongside other memory notes.

The pipeline does the following before writing:

1. **Skips trivial sessions** — fewer than 2 messages means no real conversation occurred. Additionally, sessions with 2 messages (a single exchange) are skipped unless they demonstrate substance: at least one tool was used, or total user text is >= 100 characters. This prevents "hello"/"hi" exchanges from polluting the searchable knowledge base while still preserving them in the JSON session history for resume/sidebar display.
2. **Generates a title** — first line of the first user message, truncated to 80 characters with a `...` suffix if cut. This is distinct from the JSON file title, which is a plain 100-character truncation of the full first user message.
3. **Extracts tags** — the `tools_used` set is mapped to semantic tags (e.g., `write_note` → `"writing"`, `create_plan` → `"planning"`). Every note gets the base tag `"conversation"`.
4. **Extracts topics** — simple frequency analysis over user message text. Words under 4 characters and a hardcoded stop-word list (English + Polish) are excluded. The top 5 words are returned; the top 3 are appended to the tag list.
5. **Formats the body** — a readable Markdown transcript, a `## Related Notes` section using Obsidian wiki-link syntax (`[[path|label]]`) so the graph picks up edges to any notes accessed during the session, and a `## Topics` section for keyword searchability.
6. **Indexes in SQLite** — calls `memory_service.index_note_file` so the note is immediately queryable. Failures are swallowed to avoid blocking the save.
7. **Rebuilds the knowledge graph** — calls `graph_service.rebuild_graph` so the new conversation node and its note edges appear immediately. Failures are also swallowed.

### Frontend

`useSessions` is a thin composable that wraps the API calls from `useApi` and maintains two pieces of reactive state: the list of session metadata and the currently active session ID. Deleting a session updates both the server and the local list, and clears `activeSessionId` if the deleted session was selected. The delete handler in `main.vue` wraps the call in try/catch so a failed API delete does not leave the UI in an inconsistent state.

`main.vue` keeps the session list in sync with the backend via two watchers: one fires when `chat.sessionId` changes (i.e., the WebSocket emits a `session_start` event for a new or resumed session), and the other fires when `isLoading` transitions from true to false (response complete, so the session title/preview may have updated). Both call `loadSessions()` to refresh the sidebar immediately rather than waiting for a page reload.

`SessionHistory.vue` is a presentational sidebar component. It receives `sessions` and `activeSessionId` as props and emits `select`, `new-session`, and `delete` events upward. The delete button is always present in the DOM but rendered at `opacity: 0` and revealed on item hover via CSS — it is not conditionally mounted. Deletion goes through a `ConfirmDialog` before the `delete` event is emitted; the actual API call happens in the parent that handles the event.

## Key Files

- `backend/routers/sessions.py` — REST endpoint definitions for listing, loading, resuming, and deleting sessions.
- `backend/services/session_service.py` — All session logic: in-memory store, disk persistence, resume, delete, and the conversation-to-memory pipeline including topic extraction and Markdown formatting.
- `frontend/app/composables/useSessions.ts` — Reactive session list and active-session state; wraps API calls for session operations.
- `frontend/app/components/SessionHistory.vue` — Sidebar list UI with hover-reveal delete and confirmation dialog.

## API / Interface

### REST Endpoints (`/api/sessions`)

```
GET    /api/sessions?limit=20        List saved sessions (metadata only)
GET    /api/sessions/{session_id}    Load full session including messages
POST   /api/sessions/{session_id}/resume   Rehydrate session into active store
DELETE /api/sessions/{session_id}    Delete from memory and disk
```

**`GET /api/sessions`** response (array of `SessionMetadata`):
```typescript
{
  session_id: string
  title: string        // first 100 chars of first user message
  created_at: string   // ISO 8601 UTC
  message_count: number
}
```

**`GET /api/sessions/{session_id}`** response (`SessionDetail`):
```typescript
{
  session_id: string
  title: string
  created_at: string
  ended_at: string
  message_count: number
  messages: Array<{ role: 'user' | 'assistant', content: string }>
  tools_used: string[]
  notes_accessed: string[]
}
```

**`POST /api/sessions/{session_id}/resume`** response:
```typescript
{ session_id: string, status: 'resumed' }
```

**`DELETE /api/sessions/{session_id}`** response:
```typescript
{ status: 'deleted', session_id: string }
```

### Service functions (called internally by chat router)

```python
create_session() -> str
add_message(session_id, role, content) -> None
get_messages(session_id) -> list[dict]
record_tool_use(session_id, tool_name) -> None
record_note_access(session_id, note_path) -> None
save_session(session_id) -> None
list_sessions(workspace_path, limit) -> List[dict]  # async
save_session_to_memory(session_id) -> Optional[str]  # async
```

### `useSessions` composable

```typescript
const {
  sessions,        // Ref<SessionMetadata[]>
  activeSessionId, // Ref<string | null>
  loadSessions,    // () => Promise<void>
  selectSession,   // (id: string) => Promise<SessionDetail>
  resume,          // (id: string) => Promise<void>
  removeSession,   // (id: string) => Promise<void>
  clearActive,     // () => void
} = useSessions()
```

## Gotchas

**Trivial sessions are silently ignored.** `save_session` and `list_sessions` require at least 2 messages (a complete user+assistant exchange). `save_session_to_memory` has a stricter check: a single exchange must also have tool usage or >= 100 characters of user text to be promoted to a memory note. Sessions that fail the substance check are still saved as JSON (visible in the sidebar) but not written to `memory/conversations/`. No error is raised in either case.

**In-memory sessions are lost on server restart.** The `_sessions` dict is module-level and not backed by SQLite. Restarting the backend clears all active sessions. Previously saved sessions remain on disk and can be resumed, but any session that was active and not yet saved is gone.

**Delete is non-atomic.** The router calls `delete_session` (memory), `delete_session_file` (disk), and `invalidate_cache` (graph) as three separate operations. If the process crashes between them, the JSON file may remain on disk and will reappear in the next `list_sessions` call, or the graph cache may not be invalidated until the next server restart or manual rebuild.

**Topic extraction includes Polish stop words.** The stop-word list in `_extract_topics` contains common Polish words alongside English ones. The regex also matches Polish diacritics (`ąćęłńóśźżĄĆĘŁŃÓŚŹŻ`). This is intentional — the system is designed to be bilingual.

**Wiki-link paths in the conversation note use raw file paths.** The `## Related Notes` section emits `[[path/to/note.md|Label]]`. The graph service must understand this path format when parsing the note for edges. If note paths change after a session is saved, the links in the conversation note become stale.

**`save_session_to_memory` and `list_sessions` are async but `save_session` is not.** The JSON persistence path (`save_session`) is synchronous and called from `add_message` for auto-persist. `list_sessions` offloads blocking file I/O to a thread. `save_session_to_memory` is async because it calls into async memory and graph services. Callers must use `await` for both async functions.
