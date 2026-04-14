# Step 15 — Feedback Loops (Auto-Graph, Attribution, Memory Linking)

> **Goal**: Close the three core feedback loops so that every chat action
> automatically flows into graph, memory, and sessions — without user intervention.

**Status**: ⬜ Not started

---

## Implementation Priority

> **These are the 3 things users will feel most immediately.**
> If time is limited, ship these first:

| Priority | Loop | Why |
|----------|------|-----|
| **P0** | 15c. Session → Memory auto-save | Conversations stop being lost — fundamental trust |
| **P0** | 15b. Source attribution | User sees WHERE answers come from — builds confidence |
| **P0** | 15a. Auto-graph after write | Graph stays alive without manual rebuild |
| P1 | 15d. Realtime memory refresh | Nice-to-have, not blocking — user can refresh manually |

**Recommended order**: 15c → 15b → 15a → 15d

Rationale: session auto-save has the highest perceived value ("Jarvis remembers
our conversations"), attribution builds trust ("I can see the source"),
auto-graph is invisible quality (user doesn't know they needed it until it works).

---

## 15a. Auto-Graph Update After Write

**Problem**: When Claude calls `write_note` or `append_note`, the graph is NOT updated.
User must manually rebuild the graph to see new connections.

**Solution**: After `write_note`/`append_note` in `tools.py`, trigger incremental graph update.

### Backend Changes

**`backend/services/graph_service.py`** — new function:

```python
def ingest_note(note_path: str, workspace_path=None) -> None:
    """Incrementally add/update a single note in the graph without full rebuild."""
    # 1. Read the note content
    # 2. Parse frontmatter (tags, people, related)
    # 3. Remove old edges from this note_id
    # 4. Re-add node + edges
    # 5. Run entity extraction on body (lightweight, no AI)
    # 6. Save graph
```

**`backend/services/tools.py`** — after `write_note` and `append_note`:

```python
if name == "write_note":
    await memory_service.create_note(...)
    # NEW: update graph incrementally
    graph_service.ingest_note(tool_input["path"], workspace_path)
    return f"Note saved: {tool_input['path']}"
```

Same for `append_note`.

### What Exists Already
- `rebuild_graph()` does full scan — too slow for per-note updates
- `entity_extraction.extract_entities()` exists — regex-based, no AI cost
- `parse_frontmatter()` exists in `utils/markdown.py`

### Frontend Changes
None needed in this step — graph page already loads fresh data on visit.
Optional: send a WebSocket event `graph_updated` so open graph view auto-refreshes.

### Acceptance Criteria
- [ ] User asks Claude to write a note
- [ ] Graph updates within 1s (no full rebuild)
- [ ] New tags, people, and links appear in graph
- [ ] No API calls needed (entity extraction is local regex)

---

## 15b. Specialist Attribution in Chat

**Problem**: When specialists are active, the user sees badges at top of chat but
doesn't know if/how the specialist influenced the response.

**Solution**: Add specialist name prefix to streamed responses.

### Backend Changes

**`backend/routers/chat.py`** — in `_handle_message`, after getting active specialists:

```python
active = specialist_service.get_active_specialists()
if active:
    names = ", ".join(s["name"] for s in active)
    # Prepend to first text_delta event:
    attribution_prefix = f"**[{names}]** "
```

Inject into the stream: the first `text_delta` event gets the prefix prepended.

### Frontend Changes
None — ChatPanel already renders markdown, so `**[Health Guide]**` appears as bold badge.

### Acceptance Criteria
- [ ] With specialist active, response starts with bold specialist name
- [ ] With multiple specialists, shows all names: `**[Health Guide, Planner]**`
- [ ] Without specialist, no prefix (plain Jarvis response)

---

## 15c. Session → Memory Linking

**Problem**: `save_session_to_memory()` exists and creates notes in `memory/conversations/`,
but it only runs when explicitly called. No auto-trigger. No backlinks from session to notes created during that session.

**Solution**: Auto-trigger on session end + embed note links in saved session summary.

### Backend Changes

**`backend/services/session_service.py`** — in `save_session()`:

```python
def save_session(session_id, workspace_path=None):
    # ... existing save to JSON ...
    # NEW: auto-trigger memory note creation
    import asyncio
    asyncio.create_task(save_session_to_memory(session_id, workspace_path))
```

**`backend/services/session_service.py`** — enhance `save_session_to_memory()`:

```python
# Add "Notes created" section to the summary markdown:
# - List all notes accessed/created during this session
# - Include wiki-links so graph connects session note to created notes
notes_accessed = session.get("notes_accessed", [])
if notes_accessed:
    body += "\n\n## Notes Referenced\n"
    for path in notes_accessed:
        body += f"- [[{path}]]\n"
```

**`backend/routers/chat.py`** — trigger save on WebSocket disconnect:

```python
# On WS disconnect, if session has messages:
save_session(session_id, workspace_path)
```

### What Exists Already
- `save_session_to_memory()` — creates markdown note with summary
- `record_note_access()` — tracks which notes were touched during session
- `save_session()` — saves JSON to `app/sessions/`
- Session has `tools_used` and `notes_accessed` tracking

### Acceptance Criteria
- [ ] When user closes chat (WS disconnect), session auto-saves to memory
- [ ] Saved note includes links to all notes created/accessed during session
- [ ] Graph connects session summary to referenced notes via wiki-links
- [ ] Trivial sessions (< 2 messages) are not saved (existing filter)

---

## 15d. Realtime Memory Refresh (WebSocket Events)

**Problem**: When Claude writes a note during chat, the memory page doesn't update
until user manually refreshes.

**Solution**: Backend emits events via WebSocket when memory changes. Frontend listens.

### Backend Changes

**`backend/routers/chat.py`** — after tool execution in `_handle_message`:

```python
if name in ("write_note", "append_note", "create_plan", "update_plan"):
    await websocket.send_json({
        "type": "memory_changed",
        "path": tool_input["path"],
        "action": name,
    })
```

### Frontend Changes

**`frontend/app/composables/useChat.ts`** — handle new event type:

```typescript
if (data.type === 'memory_changed') {
  // Emit a custom event that memory page can listen to
  window.dispatchEvent(new CustomEvent('jarvis:memory-changed', { detail: data }))
}
```

**`frontend/app/pages/memory.vue`** — listen for changes:

```typescript
onMounted(() => {
  window.addEventListener('jarvis:memory-changed', () => loadNotes())
})
```

### Acceptance Criteria
- [ ] User asks Claude to write a note while memory page is open in another tab
- [ ] Memory list updates automatically within 2s
- [ ] No polling — event-driven via existing WebSocket
