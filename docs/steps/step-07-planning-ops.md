# Step 07 — Planning Tools + Session Persistence

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 06 — Voice](step-06-voice.md) | **Next**: [Step 08 — Knowledge Graph](step-08-knowledge-graph.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Jarvis can create plans, summarize context, save user preferences, and persist full session transcripts. The "brain dump → organized output" flow works end-to-end.

---

## Files to Create / Modify

### Backend
```
backend/
├── services/
│   ├── tools.py               # MODIFY — add create_plan, summarize_context, save_preference
│   ├── session_service.py     # MODIFY — persist sessions to disk + conversation save model
│   └── context_builder.py     # MODIFY — include preferences in context
├── routers/
│   └── sessions.py            # NEW — session history endpoints
└── models/
    └── schemas.py             # MODIFY — add session + preference schemas
```

### Frontend
```
frontend/src/
├── components/
│   └── SessionHistory.vue     # NEW — list past sessions
├── views/
│   └── MainView.vue           # MODIFY — add session selector
└── types/
    └── index.ts               # MODIFY — add session types
```

---

## Specification

### New Tools

#### `create_plan`

```python
{
    "name": "create_plan",
    "description": "Create an organized plan from chaotic input. Saves as a Markdown note with checklist format. Splits items into priority groups: today, this week, later.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Plan title"},
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of items/tasks to organize"
            },
            "context": {"type": "string", "description": "Additional context for organizing"}
        },
        "required": ["title", "items"]
    }
}
```

Execution:
1. Generates a Markdown plan with sections: `## Today`, `## This Week`, `## Later`
2. Items formatted as `- [ ] task` checkboxes
3. Saves to `memory/plans/{date}-{slugified-title}.md`
4. Returns the saved path and formatted plan

#### `summarize_context`

```python
{
    "name": "summarize_context",
    "description": "Summarize a set of notes or conversation context into a concise summary. Saves the summary to memory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Content to summarize"},
            "title": {"type": "string", "description": "Summary title"},
            "save": {"type": "boolean", "description": "Whether to save to memory", "default": true}
        },
        "required": ["content"]
    }
}
```

Execution:
1. Claude produces a summary (this happens naturally in the model's response)
2. If `save = true`, writes to `memory/summaries/{date}-{title}.md`
3. Frontmatter: `type: summary`, `source: conversation`, `date: ...`

#### `save_preference`

```python
{
    "name": "save_preference",
    "description": "Save a user preference or rule for how Jarvis should behave. Examples: response style, priority sources, language preferences.",
    "input_schema": {
        "type": "object",
        "properties": {
            "rule": {"type": "string", "description": "The preference or rule to save"},
            "category": {"type": "string", "description": "Category: style, sources, behavior, format", "default": "general"}
        },
        "required": ["rule"]
    }
}
```

Execution:
1. Appends to `memory/preferences/rules.md` (single file, growing list)
2. Format: `- [{category}] {rule}` with timestamp
3. File has frontmatter: `type: preferences`, `updated_at: ...`

### Preferences in Context

Update `context_builder.py`:
1. Always load `memory/preferences/rules.md` if it exists
2. Append preferences to system prompt as:
   ```
   User preferences:
   - [style] Keep responses concise, under 3 paragraphs
   - [sources] Use my health notes before general knowledge
   - [behavior] Always ask before creating new notes
   ```
3. Keep preferences section under ~500 tokens — truncate oldest if too long

### Session Persistence (`session_service.py`)

#### Save Model

After each session (on WebSocket close or explicit save), write:

```json
// app/sessions/{session_id}.json
{
  "session_id": "abc123",
  "started_at": "2026-04-12T09:00:00",
  "ended_at": "2026-04-12T09:15:00",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "tools_used": ["search_notes", "create_plan"],
  "notes_created": ["plans/2026-04-12-week-plan.md"],
  "notes_referenced": ["projects/jarvis.md"]
}
```

#### Optional Post-Session Processing

After session save, optionally:
1. Generate a 1-2 sentence session summary
2. Save to `memory/summaries/{date}-session-{id}.md`
3. Extract action items mentioned → save to `memory/inbox/`

This is **optional on MVP** — can be triggered manually ("Summarize this session") or automated later.

### Session History Endpoints

#### `GET /api/sessions?limit=20`

Returns list of past sessions (metadata only):
```json
[
  {
    "session_id": "abc123",
    "started_at": "2026-04-12T09:00:00",
    "message_count": 8,
    "preview": "Planned my week, created health checklist"
  }
]
```

#### `GET /api/sessions/{session_id}`

Returns full session with all messages.

#### `POST /api/sessions/{session_id}/resume`

Loads a past session's messages as context for a new chat.

---

### Frontend

#### `SessionHistory.vue`

- Dropdown or sidebar list of past sessions
- Each entry shows: date, time, message count, preview
- Click to view or resume a session
- Accessible from MainView header

---

## Key Decisions

- Plans use checkbox Markdown format (`- [ ]`) — Obsidian-compatible
- Preferences stored in a single growing file, not one-per-rule
- Session files are JSON (not Markdown) — they're operational data, not user knowledge
- Post-session summarization is optional on MVP — avoid extra API calls
- Context builder always includes preferences — they affect every response

---

## Acceptance Criteria

- [ ] User says "plan my week" → Claude creates organized plan → saved to `memory/plans/`
- [ ] Plan has `## Today`, `## This Week`, `## Later` sections with checkboxes
- [ ] User says "keep responses shorter" → saved as preference
- [ ] Future responses respect saved preferences
- [ ] Sessions saved to `app/sessions/` on close
- [ ] Session history visible in UI
- [ ] Can resume a past session
- [ ] Preferences loaded into system prompt on every request

---

## Tests

### Backend — `tests/test_planning_service.py` (~12 tests)
- `test_create_plan_creates_file` → plan file in `memory/plans/`
- `test_plan_has_date_in_filename` → `2026-04-12-weekly.md` format
- `test_plan_has_sections` → contains Today, This Week, Later headings
- `test_plan_has_checkboxes` → tasks as `- [ ]` items
- `test_plan_indexed_in_sqlite` → plan appears in note index
- `test_update_plan_toggles_checkbox` → `- [ ]` → `- [x]` in file
- `test_update_plan_preserves_other_tasks` → untouched tasks unchanged
- `test_list_plans_sorted_by_date` → newest first
- `test_list_plans_empty` → `[]` when no plans
- `test_get_plan_content` → returns full markdown
- `test_create_plan_via_tool` → Claude tool `create_plan` works
- `test_update_plan_via_tool` → Claude tool `update_plan` works

### Backend — `tests/test_preferences_service.py` (~10 tests)
- `test_save_preference` → written to `app/preferences.json`
- `test_save_preference_key_value` → stored as `{key: value}` pair
- `test_load_preferences_empty` → `{}` when no prefs set
- `test_load_preferences_returns_all` → all saved prefs returned
- `test_overwrite_preference` → same key updates value
- `test_delete_preference` → removes key from JSON
- `test_preferences_in_system_prompt` → system prompt includes pref text
- `test_preferences_survive_restart` → load after fresh service init
- `test_preference_via_tool` → Claude tool `set_preference` works
- `test_invalid_preference_key_rejected` → empty/null key → error

### Backend — `tests/test_session_service.py` (~14 tests)
- `test_save_session_creates_file` → JSON in `app/sessions/`
- `test_save_session_has_metadata` → id, created_at, message_count, title
- `test_save_session_has_messages` → full message history persisted
- `test_save_session_auto_title` → first user message as title
- `test_list_sessions_sorted` → newest first
- `test_list_sessions_metadata_only` → no messages in list response
- `test_list_sessions_empty` → `[]`
- `test_load_session_full` → returns all messages
- `test_load_session_not_found` → SessionNotFoundError
- `test_resume_session_restores_history` → loaded messages used in next Claude call
- `test_resume_session_appends_new` → new messages added after loaded ones
- `test_delete_session` → file removed
- `test_session_file_valid_json` → file parseable as JSON
- `test_concurrent_sessions_isolated` → two sessions don't share state

### Backend — `tests/test_planning_api.py` (~6 tests)
- `test_get_plans_200` → 200 + list
- `test_post_plan_201` → 201 + plan path
- `test_patch_plan_task_200` → 200 + updated
- `test_get_sessions_200` → 200 + list
- `test_get_session_by_id_200` → 200 + full session
- `test_get_session_404` → 404 for nonexistent

### Frontend — `tests/pages/main.test.ts` additions (~4 tests)
- Session list sidebar renders
- Click session loads its messages into chat
- Active session highlighted in sidebar
- New session button clears chat

### Frontend — `tests/composables/usePreferences.test.ts` (~4 tests)
- `loadPreferences()` fetches from API
- `setPreference(key, value)` sends PATCH
- Preferences available as reactive state
- Optimistic update: UI updates before API confirms

### Regression suite
```bash
cd backend && python -m pytest tests/ -v           # ALL backend
cd frontend && npx vitest run                       # ALL frontend
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~138 backend tests
cd frontend && npx vitest run                      # ~111 frontend tests
```

**Expected total: ~249 tests**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all ~138 backend tests pass (including regression)
- [ ] `npx vitest run` — all ~111 frontend tests pass (including regression)
- [ ] Manual: "plan my week" creates plan; "keep responses shorter" persists preference
- [ ] Sessions persist and can be resumed
- [ ] Committed with message `feat: step-07 planning + sessions + preferences`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
