---
title: Specialist System
status: active
type: feature
sources:
  - backend/routers/specialists.py
  - backend/services/specialist_service.py
  - frontend/app/pages/specialists.vue
  - frontend/app/composables/useSpecialists.ts
  - frontend/app/components/SpecialistCard.vue
  - frontend/app/components/SpecialistWizard.vue
  - frontend/app/components/SpecialistBadge.vue
depends_on: [memory]
last_reviewed: 2026-04-14
---

## Summary

Specialists are named configuration profiles that adjust how Jarvis responds — narrowing its system prompt, tool access, knowledge sources, and response style without spawning a separate process or agent runtime. A user creates a specialist once through a wizard UI, then activates it on demand so that all subsequent chat turns in that session run under its constraints.

## How It Works

### Storage

Each specialist is stored as a single JSON file at `Jarvis/agents/{id}.json`. The `id` is derived by slugifying the specialist's name at creation time (e.g. "Health Guide" becomes `health-guide`). The file holds the full definition: role description, source folders, style preferences, rules, allowed tools, and up to a few example exchanges. There is no database table for specialists — the agents directory is the source of truth.

Deletion does not remove the file outright. The service moves it to `Jarvis/.trash/` so that accidental deletions can be recovered by hand.

### Activation and Session Scope

The active specialist is held in a module-level variable (`_active_specialist`) in `specialist_service.py`. This means activation is process-scoped: a single backend process has one active specialist at a time, and restarting the backend clears it. There is no persistence of which specialist was active across restarts.

When a chat request arrives, `claude.py` (or the orchestrator) calls `get_active_specialist()` and, if one is set, passes it through two functions:

- `build_specialist_prompt(specialist, base_prompt)` — appends the role, style constraints, mandatory rules, and up to two example exchanges to the base system prompt.
- `filter_tools(tools, specialist)` — reduces the available tool list to only those the specialist has been granted. If the specialist's `tools` list is empty, all tools remain available (open permission, not closed).

### Suggestion

`suggest_specialist(user_message)` performs a lightweight keyword scan: it loads every specialist from disk and checks whether the message contains the specialist's name, any of its source folder paths, or any word from its role description. The first match wins and is returned as a suggestion. This runs on every chat message when no specialist is active, enabling the UI to prompt the user.

### Creation Wizard

The frontend wizard (`SpecialistWizard.vue`) walks the user through seven steps: Name, Role, Sources, Style, Rules, Tools, and Review. Sources and rules are entered as newline-separated text and split into arrays on the fly via watchers. The `canProceed` guard only blocks progression on step 1 (name must be non-empty); all other steps are optional. On submit the form payload is emitted to the parent page, which calls `POST /api/specialists`.

### Frontend State

`useSpecialists` uses Nuxt's `useState` for shared state, meaning the `specialists` list and `activeSpecialist` detail are available globally across components without a store. The composable loads both the list and the current active specialist in a single `load()` call. Removing a specialist optimistically filters it from local state before the server confirms, and also clears `activeSpecialist` locally if the deleted specialist happened to be active.

`SpecialistBadge.vue` is a small inline component intended for the chat UI's header area. It renders the active specialist's icon and name with an `x` button to deactivate, emitting `deactivate` upward for the parent to handle.

## Key Files

- `backend/routers/specialists.py` — FastAPI router exposing CRUD, activate/deactivate, and suggest endpoints under `/api/specialists`.
- `backend/services/specialist_service.py` — All specialist logic: file I/O, slugification, prompt injection, tool filtering, keyword-based suggestion, and in-memory activation state.
- `frontend/app/pages/specialists.vue` — Specialists management page; renders the card grid and hosts the creation wizard.
- `frontend/app/composables/useSpecialists.ts` — Shared state composable for the specialist list, active specialist, and all mutation actions.
- `frontend/app/components/SpecialistCard.vue` — Card UI for a single specialist in the grid; shows source/rule counts and exposes activate/delete actions.
- `frontend/app/components/SpecialistWizard.vue` — Seven-step creation wizard; collects name, role, sources, style, rules, tool permissions, and renders a review step before emitting `save`.
- `frontend/app/components/SpecialistBadge.vue` — Compact inline badge showing the currently active specialist; used in the chat panel header to indicate active mode and allow one-click deactivation.

## API / Interface

```
GET    /api/specialists             → SpecialistSummary[]
GET    /api/specialists/active      → SpecialistDetail | { active: null }
GET    /api/specialists/suggest?message=<str>  → { suggested: SpecialistSummary | null }
GET    /api/specialists/{id}        → SpecialistDetail
POST   /api/specialists             → SpecialistDetail          (body: partial specialist dict)
PUT    /api/specialists/{id}        → SpecialistDetail          (body: partial specialist dict)
DELETE /api/specialists/{id}        → { status: "deleted" }
POST   /api/specialists/activate/{id}  → { status: "activated", specialist: SpecialistDetail }
POST   /api/specialists/deactivate     → { status: "deactivated" }
```

`SpecialistSummary` (list view, returned by `list_specialists`):
```typescript
{
  id: string
  name: string
  icon: string
  source_count: number
  rule_count: number
}
```

`SpecialistDetail` (full record, stored in `agents/{id}.json`):
```typescript
{
  id: string
  name: string
  role: string
  sources: string[]          // workspace-relative folder paths
  style: {
    tone?: string
    format?: string
    length?: string
  }
  rules: string[]
  tools: string[]            // allowed tool names; empty means all tools allowed
  examples: { user: string; assistant: string }[]
  icon: string
  created_at: string         // ISO 8601 UTC
  updated_at: string
}
```

## Gotchas

**Activation does not survive backend restarts.** The active specialist is a module-level Python variable with no persistence. If the backend process restarts mid-session, the specialist is silently deactivated and the chat reverts to base behavior with no notification to the frontend.

**Empty `tools` list means unrestricted, not locked down.** `filter_tools` returns all tools when `specialist.tools` is empty. A newly created specialist that skips the tools step can therefore use every tool. This is the open-by-default design choice — not a bug — but it means the absence of a `tools` list should not be read as "no tools allowed."

**Suggestion uses substring matching across role words.** The keyword extraction for `suggest_specialist` splits the role description on whitespace and checks each word individually. Short or common words in a role description (e.g. "a", "the", "and") will match almost any user message, producing false positives. In practice this is mitigated by the specialist name and source paths being checked first, but a role like "A general assistant for everything" would trigger a suggestion on nearly every message.

**`/api/specialists/activate/{id}` route ordering.** The `POST /api/specialists/activate/{id}` route is registered after `POST /api/specialists` in the router. FastAPI resolves this correctly because `activate` is a fixed path segment, not a parameter — but adding any future `POST /api/specialists/{action}` pattern would collide with the existing `POST /api/specialists/{spec_id}` update route if the intent were a PUT-style update via POST.

**Wizard examples field is not exposed in the UI.** `SpecialistWizard.vue` initializes `form.examples` as an empty array but has no step for adding example exchanges. Examples can only be provided by editing the JSON file directly or via `PUT /api/specialists/{id}` after creation.

## Known Issues

### Critical

**Path traversal via `spec_id` (`specialist_service.py` lines 56, 62, 93, 100, 108).** The `spec_id` parameter comes directly from the HTTP path (e.g. `GET /api/specialists/{spec_id}`) and is used without sanitization to build file paths: `_agents_dir() / f"{spec_id}.json"`. A caller that supplies a value like `../../app/config` can read, overwrite, or delete arbitrary files within the workspace — and potentially outside it depending on the OS path resolution. Every function that constructs a path from `spec_id` (`get_specialist`, `update_specialist`, `delete_specialist`, `activate_specialist`) is affected. Fix: validate that `spec_id` matches a safe pattern (e.g. `^[a-z0-9-]+$`) before constructing any path, and confirm the resolved path stays within `_agents_dir()`.

### Medium

**Silent overwrite on ID collision (`specialist_service.py` line 56).** The slug derived from a specialist's name is used as the file name with no collision check. Creating two specialists whose names slugify to the same string (e.g. "Health Guide" and "Health  Guide") silently overwrites the first specialist's JSON file. The original data is gone without warning. Fix: check whether the target file already exists before writing and raise a `ValueError` if it does, or append a numeric suffix to make the ID unique.

**Trash directory does not handle name collisions on repeated deletion (`specialist_service.py` line 109).** `delete_specialist` moves the specialist file to `Jarvis/.trash/{spec_id}.json`. If the same specialist ID is deleted more than once (possible if a file is restored manually and then deleted again), `shutil.move` silently overwrites the earlier trash entry. The first deleted version is lost. Fix: append a timestamp or counter to the trash filename to avoid collisions.

**`submit()` in `SpecialistWizard.vue` emits without validating fields beyond name (`SpecialistWizard.vue` line 148).** The `canProceed` guard only enforces a non-empty name on step 1. By step 7 the "Create Specialist" button is enabled regardless of whether any other field is filled in, and `submit()` emits the raw form state with no additional checks. A specialist with an empty role, no sources, and no rules is valid from the wizard's perspective. This is partially by design (all fields after name are optional) but callers should be aware the backend will accept whatever the wizard sends.

**`suggest_specialist` keyword matching is overly broad (`specialist_service.py` lines 182–185).** The suggestion algorithm tokenizes the specialist's role description on whitespace and tests each token as a substring against the user's message. Short, common words that appear in any role description — "a", "the", "for", "your", "all", "is" — will match nearly any user message, causing the first specialist with such a word in its role to always be suggested. The name check and source-path check run first and will short-circuit before reaching the role words, so in practice the issue only surfaces for users whose specialists do not have name/source matches. Fix: filter stopwords from the keyword list, require a minimum token length, or replace the heuristic with a more targeted approach such as checking only noun phrases or explicit topic tags.
