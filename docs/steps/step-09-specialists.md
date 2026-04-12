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

### Backend — `tests/test_specialist_service.py`
- `test_create_specialist` → JSON saved to `agents/` with correct schema
- `test_activate_specialist` → system prompt modified with specialist persona
- `test_deactivate_specialist` → system prompt reverts to base
- `test_specialist_scoped_search` → search limited to specialist source folders
- `test_specialist_tool_filter` → only permitted tools available
- `test_specialist_rules_enforced` → blocked actions return rule violation
- `test_edit_specialist` → JSON file updated
- `test_delete_specialist` → moved to `.trash/`, not permanent
- `test_suggest_specialist` → returns matching specialist for topic

### Backend — `tests/test_specialist_api.py`
- `test_post_specialist` → 201 + created
- `test_get_specialists` → 200 + list
- `test_put_specialist` → 200 + updated
- `test_delete_specialist` → 200 + trashed
- `test_post_activate` → 200 + active
- `test_post_deactivate` → 200 + base mode

### Frontend — `src/__tests__/views/SpecialistWizard.test.ts`
- Wizard renders 7 steps
- Each step validates before advancing
- Submit creates specialist via API
- Specialist badge shows when active

### Run
```bash
cd backend && python -m pytest tests/test_specialist_service.py tests/test_specialist_api.py -v
cd frontend && npx vitest run src/__tests__/views/SpecialistWizard.test.ts
```

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/test_specialist_service.py tests/test_specialist_api.py` — all pass
- [ ] `npx vitest run` — all pass
- [ ] Manual: create specialist → activate → verify scoped behavior
- [ ] Delete specialist → verify in `.trash/`
- [ ] Committed with message `feat: step-09 specialist system`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
