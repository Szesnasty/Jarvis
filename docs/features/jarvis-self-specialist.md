# JARVIS-self specialist

A built-in specialist that gives the user a direct handle on **Jarvis's own
system prompt**. It is rendered separately at the top of the Specialists page
and behaves differently from regular user-created specialists.

## Why this exists

Jarvis ships with a default system prompt that defines its core persona,
language rules, and behavior. The user should be able to:

1. **Override** that default entirely (write their own from scratch), or
2. **Extend** it with extra rules (sign-offs, format preferences, forbidden topics)

…without exposing the default prompt itself. The default is intentionally
hidden so the user writes their override **from a blank canvas**, not by
editing Anthropic-style prose they did not write.

## Two editable fields, nothing else

| Field                | Default | Purpose                                                    |
|----------------------|---------|------------------------------------------------------------|
| `system_prompt`      | `""`    | When non-empty, **replaces** the default Jarvis prompt     |
| `behavior_extension` | `""`    | When non-empty, **appended after** whatever prompt is in use |

Both are capped at `JARVIS_PROMPT_MAX_CHARS` (16 000 chars) by
[backend/models/schemas.py](../../backend/models/schemas.py). Anything else
sent in the payload (`name`, `icon`, `tools`, …) is silently ignored.

## How the prompt gets assembled

In [backend/services/claude.py](../../backend/services/claude.py)
`build_system_prompt_with_stats`:

```
base = jarvis.system_prompt if non-empty else SYSTEM_PROMPT  (default)
if other active specialists:
    base = build_multi_specialist_prompt(other_specialists, base)
if jarvis.behavior_extension non-empty:
    base += "\n\n## JARVIS — user-defined behavior extensions\n" + extension
prompt = base + retrieved_context + language_reminder
```

JARVIS is filtered out of the active-specialists loop so its content is
applied exactly once, in the order shown.

## Protections

The `jarvis` ID is reserved and the service layer enforces three guarantees:

| Operation                                | Result            | Source                                    |
|------------------------------------------|-------------------|-------------------------------------------|
| `DELETE /api/specialists/jarvis`         | `403 Forbidden`   | `delete_specialist` raises `ValueError`   |
| `POST /api/specialists/activate/jarvis`  | `400 Bad Request` | `activate_specialist` raises `ValueError` |
| `PUT  /api/specialists/jarvis` (generic) | `403 Forbidden`   | `update_specialist` raises `ValueError`   |

The only way to mutate JARVIS is through the dedicated endpoint:

- `GET  /api/specialists/jarvis/config` → returns `{system_prompt, behavior_extension}`
- `PUT  /api/specialists/jarvis/config` → whitelists those two fields only

The default Jarvis `SYSTEM_PROMPT` is **never** returned by the API.

## Seeding

`seed_builtin_specialists()` in
[backend/services/specialist_service.py](../../backend/services/specialist_service.py)
creates `~/Jarvis/agents/jarvis.json` on first run with both editable fields
empty (`""`). The seed is idempotent: it only writes when the on-disk value
differs from the built-in default.

## Frontend

[`JarvisSelfCard.vue`](../../frontend/app/components/JarvisSelfCard.vue) is
rendered above the regular specialist grid in
[specialists.vue](../../frontend/app/pages/specialists.vue). The card:

- Loads the user's current config on mount
- Shows a checkbox **"Override Jarvis's default system prompt"**. Checked
  reveals an empty textarea (the default prompt is **never** prefilled)
- Always shows a second textarea for behavior extensions
- Has a single **Save** button enabled only when the form is dirty
- Filters `jarvis` out of the regular grid and the count badge

## Tests

[backend/tests/test_jarvis_self.py](../../backend/tests/test_jarvis_self.py)
covers:

- Built-in registration and empty defaults
- Seed creates `jarvis.json` and is idempotent
- Cannot delete / activate / generic-update JARVIS
- `update_jarvis_self` whitelists only the two allowed fields
- Default flow uses built-in `SYSTEM_PROMPT`
- Override fully replaces the default in the assembled prompt
- Extension appears under the `## JARVIS — user-defined behavior extensions` heading
- HTTP layer: GET/PUT, oversize rejection (422), 403/400 protections

## Source map

| File                                                                                             | Role                                       |
|--------------------------------------------------------------------------------------------------|--------------------------------------------|
| [backend/services/specialist_service.py](../../backend/services/specialist_service.py)           | `JARVIS_SELF_ID`, builtin entry, protections, `update_jarvis_self`, `get_jarvis_self` |
| [backend/services/claude.py](../../backend/services/claude.py)                                   | Wires override + extension into `build_system_prompt_with_stats` |
| [backend/routers/specialists.py](../../backend/routers/specialists.py)                           | `GET/PUT /api/specialists/jarvis/config` + 403/400 mappings |
| [backend/models/schemas.py](../../backend/models/schemas.py)                                     | `JarvisSelfConfigRequest/Response`, `JARVIS_PROMPT_MAX_CHARS` |
| [frontend/app/components/JarvisSelfCard.vue](../../frontend/app/components/JarvisSelfCard.vue)   | Dedicated card UI                          |
| [frontend/app/composables/useApi.ts](../../frontend/app/composables/useApi.ts)                   | `fetchJarvisConfig`, `updateJarvisConfig`  |
| [frontend/app/pages/specialists.vue](../../frontend/app/pages/specialists.vue)                   | Renders card on top, filters `jarvis` out of grid |
| [frontend/app/types/index.ts](../../frontend/app/types/index.ts)                                 | `JarvisSelfConfig` type                    |
