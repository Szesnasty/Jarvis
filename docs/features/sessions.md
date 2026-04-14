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
---

# Session Management

## Summary

Sessions are the unit of a single conversation with Jarvis. Each session tracks the message history, which tools were called, and which memory notes were touched. When a session ends, it can be persisted both as a JSON file for later resumption and as a Markdown note in `memory/conversations/` so the conversation becomes part of the searchable knowledge base.

## How It Works

### In-memory store and lifecycle

Active sessions live in a module-level dict (`_sessions`) in `session_service.py`. This is a deliberate simplicity choice for MVP: no database round-trips during an active conversation. A session is created with a 12-character hex UUID, starts with an empty message list, and tracks two sets: `tools_used` and `notes_accessed`. The `tools_used` set is initialized at creation; `notes_accessed` is initialized lazily via `setdefault` on first access. Both sets accumulate passively as the chat service calls `record_tool_use` and `record_note_access` during tool execution.

Message history is trimmed to the most recent 20 messages (`MAX_HISTORY_MESSAGES`) on every append, keeping the in-memory footprint bounded and preventing unbounded growth in long conversations.

### Persistence to disk (JSON)

`save_session` writes the active session to `{workspace}/app/sessions/{session_id}.json`. Sessions with zero messages are silently skipped — this prevents empty sessions from cluttering the history list. The title stored in the JSON file is the first 100 characters of the first user message (raw truncation, no ellipsis).

`list_sessions` reads and fully parses every JSON file in the sessions directory, extracts the metadata fields (id, title, created_at, message_count), and returns them sorted newest-first. The `limit` parameter is applied by the router as a slice after the full directory scan — all files are always read regardless of limit. Corrupt or unreadable files are skipped individually rather than failing the entire list.

### Resume flow

`resume_session` rehydrates a persisted session back into the in-memory store by reading its JSON file. The session ID stays the same, so the caller can resume sending messages as if the conversation never ended. The `tools_used` and `notes_accessed` fields are converted back from lists (JSON) to sets (Python) on load.

### Delete flow

Deletion is two steps, both called from the router: `delete_session` removes the in-memory entry, and `delete_session_file` removes the JSON file from disk. If the session was never saved (e.g., empty), `delete_session_file` is a no-op.

### Conversation-to-memory pipeline

`save_session_to_memory` is the more significant write path. It converts a completed session into a Markdown note at `memory/conversations/{date}-{time}-{slug}.md`. This is what makes conversations searchable alongside other memory notes.

The pipeline does the following before writing:

1. **Skips trivial sessions** — fewer than 2 messages means no real conversation occurred.
2. **Generates a title** — first line of the first user message, truncated to 80 characters with a `...` suffix if cut. This is distinct from the JSON file title, which is a plain 100-character truncation of the full first user message.
3. **Extracts tags** — the `tools_used` set is mapped to semantic tags (e.g., `write_note` → `"writing"`, `create_plan` → `"planning"`). Every note gets the base tag `"conversation"`.
4. **Extracts topics** — simple frequency analysis over user message text. Words under 4 characters and a hardcoded stop-word list (English + Polish) are excluded. The top 5 words are returned; the top 3 are appended to the tag list.
5. **Formats the body** — a readable Markdown transcript, a `## Related Notes` section using Obsidian wiki-link syntax (`[[path|label]]`) so the graph picks up edges to any notes accessed during the session, and a `## Topics` section for keyword searchability.
6. **Indexes in SQLite** — calls `memory_service.index_note_file` so the note is immediately queryable. Failures are swallowed to avoid blocking the save.
7. **Rebuilds the knowledge graph** — calls `graph_service.rebuild_graph` so the new conversation node and its note edges appear immediately. Failures are also swallowed.

### Frontend

`useSessions` is a thin composable that wraps the API calls from `useApi` and maintains two pieces of reactive state: the list of session metadata and the currently active session ID. Deleting a session updates both the server and the local list, and clears `activeSessionId` if the deleted session was selected.

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

**Empty sessions are silently ignored.** `save_session` and `save_session_to_memory` both return early if the session has no messages (or fewer than 2 for the memory pipeline). No error is raised. If a session disappears from the history list after what looked like a conversation, the most likely cause is that messages were never recorded against that session ID.

**In-memory sessions are lost on server restart.** The `_sessions` dict is module-level and not backed by SQLite. Restarting the backend clears all active sessions. Previously saved sessions remain on disk and can be resumed, but any session that was active and not yet saved is gone.

**Delete is non-atomic.** The router calls `delete_session` (memory) and then `delete_session_file` (disk) as two separate operations. If the process crashes between them, the JSON file remains on disk and will reappear in the next `list_sessions` call, but the in-memory entry will be gone — resume will work correctly to reload it.

**Topic extraction includes Polish stop words.** The stop-word list in `_extract_topics` contains common Polish words alongside English ones. The regex also matches Polish diacritics (`ąćęłńóśźżĄĆĘŁŃÓŚŹŻ`). This is intentional — the system is designed to be bilingual.

**Wiki-link paths in the conversation note use raw file paths.** The `## Related Notes` section emits `[[path/to/note.md|Label]]`. The graph service must understand this path format when parsing the note for edges. If note paths change after a session is saved, the links in the conversation note become stale.

**`save_session_to_memory` is async but `save_session` is not.** The JSON persistence path is synchronous; the memory pipeline path is async (it calls into async memory and graph services). Callers must use `await` for `save_session_to_memory` or the indexing and graph rebuild steps will not complete.

## Known Issues

### Critical

**Path traversal in `load_session` and `delete_session_file` (`session_service.py:139,161`).** The `session_id` parameter arrives from the URL path and is used directly to construct a file path via `d / f"{session_id}.json"`. No validation or sanitization is applied. A `session_id` containing `../` sequences (e.g., `../../etc/passwd`) would allow an attacker to read or delete arbitrary files within the backend process's permissions. Fix: validate that `session_id` matches an expected format (e.g., `^[a-f0-9]{12}$`) before using it in path construction, and/or use `.resolve()` to confirm the resolved path stays inside the sessions directory.

### High

**In-memory state is never auto-persisted; a crash loses all active session data.** `save_session` is only called explicitly by callers (e.g., at the end of a chat turn or on session close). If the backend process crashes or is killed between explicit saves, the entire `_sessions` dict is lost — including all messages, tool use records, and note access records for every session that was in progress. Sessions that had been explicitly saved previously can still be resumed from disk, but anything since the last save is unrecoverable.

### Medium

**`_extract_topics` crashes on non-string message content (`session_service.py:186`).** The function joins message content with `" ".join(m["content"] for m in messages if m["role"] == "user")`. Claude's multi-modal responses (and tool-use blocks from the Anthropic API) can produce `content` values that are lists of content blocks rather than strings, which causes a `TypeError` at join time. This would surface as an unhandled exception inside `save_session_to_memory`, likely causing the memory note to not be written. Fix: coerce content to string before joining (e.g., `str(m["content"])` or extract only `text`-type blocks).

**`list_sessions` always scans all files regardless of the requested limit (`sessions.py:11`).** `session_service.list_sessions()` reads and fully parses every `.json` file in the sessions directory before returning. The router then applies `[:limit]` as a Python slice on the complete result. As the sessions directory grows, this becomes an O(n) disk read on every call to the history endpoint, even when only the 20 most recent sessions are needed. Fix: either store metadata separately (e.g., in SQLite) or at minimum apply early exit once enough sessions are collected after sorting.
