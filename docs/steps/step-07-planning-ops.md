# Step 07 — Planning Tools + Session Persistence

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 06 — Voice](step-06-voice.md) | **Next**: [Step 08 — Knowledge Graph](step-08-knowledge-graph.md) | **Index**: [step-00-index.md](step-00-index.md)

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
