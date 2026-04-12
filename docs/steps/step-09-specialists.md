# Step 09 — Specialist System + UI Wizard

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 08 — Knowledge Graph](step-08-knowledge-graph.md) | **Next**: [Step 10 — Polish](step-10-polish.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Users can create, manage, and activate custom specialists from the UI. Specialists modify Jarvis's behavior with custom knowledge, rules, and style — without being separate agents.

---

## Files to Create / Modify

### Backend
```
backend/
├── routers/
│   └── specialists.py         # NEW — CRUD endpoints for specialists
├── services/
│   ├── specialist_service.py  # NEW — specialist management
│   ├── claude.py              # MODIFY — apply specialist config to prompts
│   ├── context_builder.py     # MODIFY — scope retrieval to specialist sources
│   └── tools.py               # MODIFY — filter tools by specialist permissions
└── models/
    └── schemas.py             # MODIFY — add specialist schemas
```

### Frontend
```
frontend/src/
├── views/
│   └── SpecialistsView.vue    # NEW — list + manage specialists
├── components/
│   ├── SpecialistCard.vue     # NEW — specialist preview card
│   ├── SpecialistWizard.vue   # NEW — multi-step creation wizard
│   └── SpecialistBadge.vue    # NEW — active specialist indicator
├── router/
│   └── index.ts               # MODIFY — add /specialists route
├── stores/
│   └── app.ts                 # MODIFY — track active specialist
├── services/
│   └── api.ts                 # MODIFY — add specialist API calls
└── types/
    └── index.ts               # MODIFY — add specialist types
```

---

## Specification

### What a Specialist Is

**A specialist is not a separate autonomous agent runtime. It is a constrained configuration profile used by Jarvis Core.**

When a specialist is active, Jarvis Core:
1. Prepends the specialist's role to the system prompt
2. Scopes retrieval to the specialist's assigned sources
3. Applies the specialist's rules and style
4. Limits available tools to the specialist's permissions
5. Uses the specialist's examples for few-shot guidance (if provided)

No separate process. No task queue. No independent memory.

### Data Model

Stored as `Jarvis/agents/{specialist-id}.json`:

```json
{
  "id": "health-guide",
  "name": "Health Guide",
  "role": "You are a health-focused assistant that helps track symptoms, medication, and wellness using the user's health notes.",
  "sources": [
    "memory/knowledge/health/",
    "memory/daily/"
  ],
  "style": {
    "tone": "calm, supportive",
    "format": "checklist",
    "length": "concise"
  },
  "rules": [
    "Never diagnose conditions",
    "Always reference the user's own notes first",
    "Separate user's data from general knowledge",
    "Ask clarifying questions about symptoms"
  ],
  "tools": [
    "search_notes",
    "read_note",
    "write_note",
    "append_note",
    "create_plan",
    "query_graph"
  ],
  "examples": [
    {
      "user": "How has my sleep been?",
      "assistant": "Based on your last 5 daily notes, your average sleep has been...\n- Mon: 6.5h\n- Tue: 7h\n- Wed: 5h (noted headache)\n..."
    }
  ],
  "icon": "🏥",
  "created_at": "2026-04-12T10:00:00",
  "updated_at": "2026-04-12T10:00:00"
}
```

### Specialist API

#### `GET /api/specialists`

Returns list of all specialists (metadata):
```json
[
  {"id": "health-guide", "name": "Health Guide", "icon": "🏥", "source_count": 2, "rule_count": 4}
]
```

#### `GET /api/specialists/{id}`

Full specialist config.

#### `POST /api/specialists`

Create new specialist. Generates `id` from slugified name.

#### `PUT /api/specialists/{id}`

Update specialist config.

#### `DELETE /api/specialists/{id}`

Soft-delete (move JSON to `.trash/`).

### Applying Specialist Config

When specialist is active, modify Claude call:

```python
# claude.py
async def build_specialist_prompt(specialist: Specialist, base_prompt: str) -> str:
    sections = [base_prompt]

    # Role
    sections.append(f"\n## Active Specialist: {specialist.name}\n{specialist.role}")

    # Style
    if specialist.style:
        style_str = f"Tone: {specialist.style.tone}. Format: {specialist.style.format}. Length: {specialist.style.length}."
        sections.append(f"\nResponse style: {style_str}")

    # Rules
    if specialist.rules:
        rules_str = "\n".join(f"- {r}" for r in specialist.rules)
        sections.append(f"\nRules you MUST follow:\n{rules_str}")

    # Examples (few-shot)
    if specialist.examples:
        examples_str = ""
        for ex in specialist.examples[:2]:  # max 2 to save tokens
            examples_str += f"\nUser: {ex['user']}\nAssistant: {ex['assistant']}\n"
        sections.append(f"\nExample interactions:\n{examples_str}")

    return "\n".join(sections)
```

### Scoped Retrieval

When specialist is active:
- `context_builder.py` filters search to specialist's `sources` folders
- `query_graph` focuses on subgraph connected to specialist's sources
- Tools are filtered to only those listed in specialist's `tools` array

```python
async def retrieve_for_specialist(query: str, specialist: Specialist) -> list[RetrievalResult]:
    results = await retrieval.retrieve(query, folders=specialist.sources, limit=5)
    return results
```

### Specialist Activation

#### Manual activation (via chat):
User says: "Use Health Guide" or "Switch to Weekly Planner"
Claude recognizes intent, backend activates specialist.

#### Manual activation (via UI):
User clicks specialist card → specialist becomes active.

#### Suggestion from Jarvis:
When no specialist is active and topic matches specialist's sources:
```python
def suggest_specialist(user_message: str, specialists: list[Specialist]) -> Specialist | None:
    """Simple keyword matching against specialist roles and source folder names."""
    # Check if message mentions keywords related to any specialist
    ...
```

If matched, Jarvis says: "This looks health-related. Want me to use Health Guide?"

---

### Frontend

#### `SpecialistsView.vue`

- Grid of `SpecialistCard` components
- "Create new specialist" button → opens wizard
- Click card → view/edit specialist

#### `SpecialistCard.vue`

- Icon + name + role preview
- Source count, rule count
- "Activate" button
- "Edit" / "Delete" actions

#### `SpecialistWizard.vue`

Multi-step form (7 steps, consistent with plan):

1. **Name + Icon** — text input + emoji picker (or text emoji input)
2. **Role** — textarea describing what this specialist does
3. **Sources** — multi-select from memory folders + specific notes
4. **Style** — dropdowns or toggles: tone, format, length
5. **Rules** — dynamic list: add/remove rule strings
6. **Tools** — checkboxes for available tools
7. **Examples** — optional: user/assistant message pairs

Navigation: Back / Next buttons, step indicator, Save on final step.

#### `SpecialistBadge.vue`

- Small badge in MainView header showing active specialist
- Click to deactivate (return to base Jarvis)
- Shows icon + name: "🏥 Health Guide"

---

## Key Decisions

- Specialists are JSON config files — simple, portable, human-readable
- No separate runtime — Jarvis Core applies config as system prompt modifiers
- Max 2 examples in prompt to save tokens
- Source scoping at retrieval level, not at file system level (specialist can reference but not edit outside sources)
- Tool filtering: if specialist doesn't have `write_note`, Claude won't be offered that tool
- Simple keyword matching for suggestions — no AI call needed

---

## Acceptance Criteria

- [ ] User creates specialist via 7-step wizard → JSON saved to `agents/`
- [ ] Activating specialist changes Jarvis response style and knowledge scope
- [ ] Specialist rules are respected (e.g., "never diagnose" blocks diagnosis attempts)
- [ ] Search is scoped to specialist's source folders when active
- [ ] Tool list is filtered by specialist permissions
- [ ] Jarvis suggests relevant specialist when topic matches
- [ ] Specialist badge visible in main view when active
- [ ] Deactivating specialist returns to base Jarvis behavior
- [ ] Editing specialist updates JSON file
- [ ] Deleting specialist moves to `.trash/`

---

## Tests

### Backend — `tests/test_specialist_service.py` (~16 tests)
- `test_create_specialist_saves_json` → JSON file in `agents/`
- `test_create_specialist_schema` → has name, persona, sources, tools, rules
- `test_create_specialist_validates_name` → empty name rejected
- `test_list_specialists` → returns all created specialists
- `test_list_specialists_empty` → `[]` when none exist
- `test_get_specialist` → returns full JSON by id
- `test_get_specialist_not_found` → SpecialistNotFoundError
- `test_activate_specialist_modifies_prompt` → system prompt includes specialist persona
- `test_activate_specialist_sets_active` → `active_specialist` state updated
- `test_deactivate_returns_to_base` → system prompt reverts to default Jarvis
- `test_scoped_search` → search limited to specialist's `sources` folders
- `test_scoped_search_no_leakage` → notes outside scope NOT returned
- `test_tool_filter_whitelist` → only permitted tools in Claude call
- `test_tool_filter_blocks_restricted` → restricted tool not callable
- `test_rules_enforced` → rule violation returns error, not Claude response
- `test_suggest_specialist` → topic match returns specialist suggestion

### Backend — `tests/test_specialist_lifecycle.py` (~8 tests)
- `test_edit_specialist_updates_file` → JSON file changed on disk
- `test_edit_specialist_preserves_id` → id unchanged after edit
- `test_delete_specialist_moves_to_trash` → file in `.trash/`, not deleted
- `test_delete_specialist_removes_from_list` → not in `list_specialists()`
- `test_delete_active_specialist_deactivates` → auto-deactivates first
- `test_activate_nonexistent_raises` → SpecialistNotFoundError
- `test_activate_while_another_active` → previous deactivated first
- `test_specialist_survives_restart` → new service instance loads from disk

### Backend — `tests/test_specialist_api.py` (~10 tests)
- `test_post_specialist_201` → 201 + id
- `test_post_specialist_invalid` → 422 for missing required fields
- `test_get_specialists_200` → 200 + list
- `test_get_specialist_by_id_200` → 200 + full data
- `test_get_specialist_404` → 404
- `test_put_specialist_200` → 200 + updated
- `test_delete_specialist_200` → 200
- `test_post_activate_200` → 200 + active
- `test_post_deactivate_200` → 200 + deactivated
- `test_get_active_specialist` → 200 + currently active (or null)

### Frontend — `tests/pages/specialists.test.ts` (~6 tests)
- Renders list of specialists from API
- Each card shows name, description, active badge
- Click card opens detail/edit view
- Delete button calls API and removes card
- Active specialist highlighted
- Empty state shows "Create your first specialist"

### Frontend — `tests/components/SpecialistWizard.test.ts` (~10 tests)
- Wizard renders step 1 (name + description)
- Step 2: persona textarea
- Step 3: source folder picker
- Step 4: tool permissions checkboxes
- Step 5: rules textarea
- Step 6: review summary
- Step 7: submit confirmation
- Back button returns to previous step
- Validation prevents skip with empty required fields
- Submit sends POST and closes wizard

### Frontend — `tests/components/SpecialistBadge.test.ts` (~3 tests)
- Hidden when no specialist active
- Shows specialist name when active
- Click opens specialist detail

### Regression suite
```bash
cd backend && python -m pytest tests/ -v
cd frontend && npx vitest run
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~206 backend tests
cd frontend && npx vitest run                      # ~143 frontend tests
```

**Expected total: ~349 tests**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all ~206 backend tests pass (including regression)
- [ ] `npx vitest run` — all ~143 frontend tests pass (including regression)
- [ ] Manual: create specialist → activate → verify scoped behavior
- [ ] Delete specialist → verify in `.trash/`
- [ ] Scoped search verified (no leakage outside specialist sources)
- [ ] Committed with message `feat: step-09 specialist system`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
