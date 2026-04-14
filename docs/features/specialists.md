---
title: Specialist System
status: active
type: feature
sources:
  - backend/routers/specialists.py
  - backend/services/specialist_service.py
  - backend/models/schemas.py
  - frontend/app/pages/specialists.vue
  - frontend/app/composables/useSpecialists.ts
  - frontend/app/components/SpecialistCard.vue
  - frontend/app/components/SpecialistWizard.vue
  - frontend/app/components/SpecialistBadge.vue
  - frontend/app/components/SpecialistKnowledgePanel.vue
depends_on: [memory]
last_reviewed: 2026-04-15
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
- `_load_specialist_knowledge(spec_id)` (in `context_builder.py`) — reads all text-based knowledge files from `agents/{id}/` and injects them into the context sent to Claude, within a 4,000-character budget. This ensures uploaded documents are actually visible to Claude during chat.

### Suggestion

`suggest_specialist(user_message)` performs a lightweight keyword scan: it loads every specialist from disk and checks whether the message contains the specialist's name, any of its source folder paths, or any word from its role description. The first match wins and is returned as a suggestion. This runs on every chat message when no specialist is active, enabling the UI to prompt the user.

### Creation and Edit Wizard

The frontend wizard (`SpecialistWizard.vue`) walks the user through seven steps: Name, Role, Knowledge, Style, Rules, Tools, and Review. Step 3 ("Knowledge") replaces the old raw-textarea sources step with a drag-and-drop file staging area plus URL input. Files staged during creation are uploaded after the specialist is saved. The auto-created folder path `memory/specialists/{id}/` is shown read-only, with optional extra source folder paths available under an "advanced" toggle. The wizard now emits both the form data and an array of staged `File` objects to the parent page. Steps use slide transitions for directional navigation and step indicators are clickable to jump between completed steps.

The wizard supports both creation and editing through an optional `initialData` prop of type `SpecialistDetail`. When `initialData` is provided:

- The form is pre-filled with the existing specialist's data (role, sources, style, rules, tools, examples, icon).
- The Name field becomes **read-only** because the specialist ID is derived from the name and is immutable after creation.
- The submit button on the Review step reads "Save Changes" instead of "Create Specialist".
- The wizard title changes to "Edit Specialist" to reflect the mode.

The parent page (`specialists.vue`) opens the wizard in edit mode by fetching the full `SpecialistDetail` via `api.fetchSpecialist(id)` and passing it as `initialData`. On save, the page branches: if `editingSpec` is set it calls `update(id, data)`, otherwise it calls `api.createSpecialist(data)`. In both paths, any staged files are uploaded after the primary operation succeeds. Individual file upload failures are non-blocking.

### Frontend State

`useSpecialists` uses Nuxt's `useState` for shared state. In addition to the `specialists` list, `activeSpecialist`, and mutation actions, it exposes an `update(id, data)` method that calls `api.updateSpecialist()` with a partial specialist payload and then reloads the full list. It also tracks:

- `expandedId` — which specialist card is currently expanded to show its knowledge panel.
- `files` — a `Record<string, SpecialistFileInfo[]>` cache of knowledge files per specialist, keyed by ID.
- `filesLoading` — loading state per specialist for async file list fetches.

New methods: `toggleExpand(id)`, `loadFiles(id)`, `uploadFile(id, file)`, `ingestUrl(id, url)`, `removeFile(id, filename)`. Files are loaded lazily on first expand.

`SpecialistBadge.vue` is a compact inline badge in the chat panel header showing a pulsing dot, the active specialist's icon and name, and an `x` button to deactivate.

### Knowledge Panel

`SpecialistKnowledgePanel.vue` is an inline component rendered inside expanded specialist cards. It provides:

- A drag-and-drop upload zone with file browse fallback. Client-side validation enforces allowed file types (`.md`, `.txt`, `.pdf`, `.csv`, `.json`) and a 50 MB size limit — both for the browse dialog and drag-and-drop, which bypasses the HTML `accept` attribute.
- A URL ingest bar with enter-to-submit. URLs are validated with the `URL` constructor before submission; malformed input shows an inline error.
- A scrollable file list showing filename/title, size, and a delete button (visible on hover).
- Loading, empty, and error states.
- `TransitionGroup` animations on file list mutations.

File counts on specialist cards are derived from the local file cache length after successful API operations (`_syncFileCount`), not optimistic increments, so counts stay consistent even if individual uploads fail.

## Key Files

- `backend/routers/specialists.py` — FastAPI router exposing CRUD, activate/deactivate, and suggest endpoints under `/api/specialists`.
- `backend/services/specialist_service.py` — All specialist logic: file I/O, slugification, prompt injection, tool filtering, keyword-based suggestion, and in-memory activation state.
- `frontend/app/pages/specialists.vue` — Specialists management page; renders the card grid with expand/collapse, hosts the creation/edit wizard, and wires up delete confirmation via `ConfirmDialog`. Manages `editingSpec` state to switch the wizard between create and edit modes.
- `frontend/app/composables/useSpecialists.ts` — Shared state composable for the specialist list, active specialist, file cache, expand state, and all mutation actions including file CRUD and `update(id, data)` for editing.
- `frontend/app/components/SpecialistCard.vue` — Expandable card for a single specialist; shows icon with active dot, file/source/rule counts, activate/edit/delete/expand buttons, and renders `SpecialistKnowledgePanel` when expanded. The edit button (pencil icon, amber hover) emits an `edit` event. Uses scanline texture and gradient effects for active state.
- `frontend/app/components/SpecialistKnowledgePanel.vue` — Inline knowledge management panel with drag-and-drop upload, URL ingest, and file list with delete. Rendered inside expanded cards.
- `frontend/app/components/SpecialistWizard.vue` — Seven-step creation/edit wizard with slide transitions; step 3 is now a file staging area with drag-and-drop instead of raw textarea. Accepts optional `initialData` prop for edit mode (pre-fills form, locks name field, changes submit label). Emits staged files alongside form data.
- `frontend/app/components/SpecialistBadge.vue` — Compact inline badge showing the currently active specialist with pulsing dot indicator; used in the chat panel header.

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

# File management
GET    /api/specialists/{id}/files           → FileInfo[]
POST   /api/specialists/{id}/files           → FileInfo          (multipart: file upload)
DELETE /api/specialists/{id}/files/{filename} → { status: "deleted" }
POST   /api/specialists/{id}/ingest-url      → FileInfo          (body: { url, summarize? })
```

`SpecialistSummary` (list view, returned by `list_specialists`):
```typescript
{
  id: string
  name: string
  icon: string
  source_count: number
  rule_count: number
  file_count: number          // count of knowledge files in agents/{id}/
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

`FileInfo` (returned by file management endpoints):
```typescript
{
  filename: string       // "blood-results.md"
  path: string           // filename only (relative within specialist dir)
  title: string          // derived from filename: hyphens/underscores → spaces
  size: number           // bytes
  created_at: string     // ISO 8601 UTC
}
```

## File Management

### Overview

Each specialist can own knowledge files stored in `{workspace}/agents/{specialist_id}/`. These files are the specialist's curated knowledge base and are managed through dedicated API endpoints. The directory is created lazily on first file upload via `_files_dir()`.

### Storage Location

Files live alongside the specialist JSON definition under the `agents/` tree:

```
Jarvis/
├── agents/
│   ├── health-guide.json          ← specialist definition
│   ├── health-guide/              ← knowledge files directory
│   │   ├── blood-results.md
│   │   └── nutrition-article.pdf
│   ├── study-coach.json
│   └── study-coach/
│       └── learning-techniques.txt
```

> Note: The original plan proposed storing specialist files under `memory/specialists/{id}/`. The actual implementation stores them under `agents/{id}/` to keep specialist definitions and their knowledge co-located. This is a deviation from the source-of-truth doctrine (which says all user knowledge should live under `memory/`). A future migration may move files to `memory/specialists/` if Obsidian compatibility becomes important for specialist knowledge.

### Allowed File Types

| Extension | Type |
|-----------|------|
| `.md`     | Markdown |
| `.txt`    | Plain text |
| `.pdf`    | PDF document |
| `.csv`    | CSV data |
| `.json`   | JSON data |

### Size Limit

Maximum upload size is **50 MB** per file, enforced at the router level (`MAX_UPLOAD_BYTES`).

### Filename Validation

Filenames are validated by `_validate_filename()` using the pattern `^[a-zA-Z0-9][a-zA-Z0-9._\- ]{0,200}$`. Path traversal characters (`..`, `/`, `\`) are explicitly rejected. If a file with the same name already exists, the service appends an incrementing number (e.g., `notes-1.md`, `notes-2.md`) rather than overwriting.

### URL Ingest

The `POST /api/specialists/{id}/ingest-url` endpoint ingests a URL through the existing `url_ingest` service into `memory/knowledge/`, then copies the resulting file into the specialist's `agents/{id}/` directory. The URL must start with `http://` or `https://`. An optional `summarize` boolean triggers AI-powered summarization during ingest.

### Backend Functions

| Function | Description |
|----------|-------------|
| `_files_dir(spec_id)` | Returns and creates the `agents/{id}/` directory for knowledge files |
| `_validate_filename(filename)` | Validates filename format and allowed extensions |
| `list_specialist_files(spec_id)` | Lists all knowledge files with metadata (filename, title, size, created_at) |
| `save_specialist_file(spec_id, filename, content)` | Saves uploaded bytes to disk with collision avoidance |
| `delete_specialist_file(spec_id, filename)` | Permanently deletes a file (no trash) |
| `count_specialist_files(spec_id)` | Returns the count of knowledge files; used by `list_specialists()` for the `file_count` field |

## Knowledge Folders — Design History

> This section preserves the original design discussion for context. Phases 1 and 2 are now implemented. The actual implementation differs from the original proposal in storage location — see the "File Management" section above for current behavior.

### Context

Originally specialists were behavioral profiles — they adjusted prompt, style, and tool access but shared the same pool of notes as base Jarvis. The `sources` field accepts folder paths typed manually by the user, with no validation that those folders exist and no dedicated place to upload files for a specific specialist.

The goal is to make each specialist a **knowledge container**: a dedicated folder the user can fill with files (upload, URL ingest, drag-and-drop), so that the specialist answers only from its curated knowledge base. This turns specialists from "prompt profiles" into "personal experts with curated knowledge."

### Decision Drivers

- User should never need to know the folder structure — creating a specialist auto-creates its knowledge folder
- Existing ingest pipeline (file upload, URL ingest, AI enrichment) must be reused, not duplicated
- Retrieval scoping already works via `_scope_results()` in `context_builder.py` — the filter just needs the right folder paths
- Source of truth doctrine: files on disk in `memory/`, indexed in SQLite

### Proposed Architecture

#### Folder Structure

```
Jarvis/
├── memory/
│   ├── specialists/              ← new top-level folder
│   │   ├── health-guide/         ← auto-created with specialist
│   │   │   ├── blood-results.md
│   │   │   └── nutrition-article.md
│   │   ├── study-coach/
│   │   │   └── learning-techniques.md
│   │   └── weekly-planner/
│   └── knowledge/                ← shared knowledge (unchanged)
└── agents/
    ├── health-guide.json         ← specialist definition (unchanged)
    └── study-coach.json
```

`memory/specialists/{id}/` is the dedicated knowledge folder. The specialist JSON's `sources` field is auto-populated with `["memory/specialists/{id}"]` at creation time. Users can still add additional source folders manually.

#### Backend Changes

| File | Change |
|------|--------|
| `specialist_service.py` | `create_specialist()` creates `memory/specialists/{id}/` on disk and auto-sets `sources` to include it. `delete_specialist()` moves the knowledge folder to trash alongside the JSON. |
| `specialist_service.py` | New function `get_specialist_files(spec_id)` — lists files in the specialist's knowledge folder with metadata (title, size, date). |
| `routers/specialists.py` | New endpoints: `POST /api/specialists/{id}/files` (upload), `POST /api/specialists/{id}/ingest-url` (URL ingest), `GET /api/specialists/{id}/files` (list), `DELETE /api/specialists/{id}/files/{filename}` (remove). |
| `routers/memory.py` | No changes — existing `/api/memory/ingest` stays for general uploads. Specialist uploads go through specialist router. |
| `services/ingest.py` | `fast_ingest()` already accepts `folder` param. Pass `specialists/{id}` as folder. Folder regex in `memory.py` relaxed to allow one slash for nested paths: `^[a-zA-Z0-9][a-zA-Z0-9/-]*$`. |
| `services/url_ingest.py` | `ingest_url()` already accepts `folder` param. Same approach — pass `specialists/{id}`. |
| `context_builder.py` | No changes needed — `_scope_results()` already filters by path prefix. |

#### New API Endpoints

```
GET    /api/specialists/{id}/files                → FileInfo[]
POST   /api/specialists/{id}/files                → FileInfo          (multipart: file upload)
POST   /api/specialists/{id}/ingest-url           → FileInfo          (body: { url, summarize? })
DELETE /api/specialists/{id}/files/{filename}      → { status: "deleted" }
```

```typescript
interface FileInfo {
  filename: string       // "blood-results.md"
  path: string           // "specialists/health-guide/blood-results.md"
  title: string          // from frontmatter or filename
  size: number           // bytes
  created_at: string     // ISO 8601
}
```

#### Frontend Changes

| Component | Change |
|-----------|--------|
| `SpecialistCard.vue` | Add expandable "Knowledge" section showing file list with count badge. Add upload button and URL ingest input inline on the card. |
| `SpecialistWizard.vue` | Step 3 (Sources) becomes a file upload area + URL input instead of raw textarea. The auto-created folder path is shown read-only. Manual additional source paths remain as optional advanced input. |
| `useSpecialists.ts` | New methods: `loadFiles(id)`, `uploadFile(id, file)`, `ingestUrl(id, url)`, `removeFile(id, filename)`. |
| `useApi.ts` | New API methods matching the endpoints above. |

#### Tool Scoping (Hard Filter)

Currently `open_note` and `write_note` tools can access any path regardless of specialist sources. To enforce hard scoping:

- `tools.py`: when a specialist is active, `open_note` and `write_note` validate that the target path falls within the specialist's `sources` folders. Attempts to access outside scope return an error message to Claude instead of the note content.
- This is opt-in per specialist via a new boolean field `strict_scope` (default `false` for backward compatibility).

### Trade-offs

| Choice | Benefit | Cost |
|--------|---------|------|
| Auto-create folder at specialist creation | Zero friction — user never thinks about paths | Empty folders on disk for specialists that never get files |
| Specialist-scoped endpoints vs reusing `/api/memory/ingest` | Clean API, clear ownership, no param confusion | Slight code duplication (delegates to same `fast_ingest` internally) |
| `strict_scope` opt-in | Backward compatible, power users can still cross-reference | Soft scoping by default may confuse users expecting isolation |
| Folder under `memory/specialists/` vs `memory/agents/` | Separates knowledge (memory/) from config (agents/), follows source-of-truth doctrine | Two places to look for specialist-related files |

### Alternatives Considered

**Flat folder names (`memory/specialist-health-guide/`)** — avoids nested paths and regex changes but pollutes the top-level `memory/` directory. Rejected because it doesn't scale and breaks the clean folder taxonomy.

**Tag-based scoping instead of folders** — tag notes with `specialist: health-guide` and filter by tag. Rejected because it requires modifying every ingested file's frontmatter, makes it harder to bulk-manage files, and breaks the "folder = scope" mental model that's already in place.

**Separate storage outside `memory/`** — store specialist knowledge in `agents/{id}/knowledge/`. Rejected because it violates the source-of-truth doctrine: all user knowledge must live under `memory/` so it's Obsidian-compatible and rebuildable.

### Migration Path

1. **Phase 1 — Backend folder auto-creation + file endpoints.** `specialist_service.py` gained `list_specialist_files()`, `save_specialist_file()`, `delete_specialist_file()`, `count_specialist_files()`, `_files_dir()`, and `_validate_filename()`. `routers/specialists.py` gained 4 new endpoints for file CRUD and URL ingest. `schemas.py` added `SpecialistFileInfoResponse` and `file_count` on `SpecialistSummaryResponse`. Folders are created lazily on first upload. **Status: complete.**
2. **Phase 2 — Frontend UI.** Card gets file list + upload. Wizard Sources step gets drag-and-drop. Ship together with Phase 1. **Status: complete.** `SpecialistCard`, `SpecialistKnowledgePanel`, `SpecialistWizard`, `useSpecialists`, `useApi`, and `types` all implemented. Tests: 51 passing across 5 test files.
3. **Phase 3 — Hard tool scoping.** Add `strict_scope` field and enforce in `tools.py`. Optional, can ship later. **Status: not started.**

## Gotchas

**Activation does not survive backend restarts.** The active specialist is a module-level Python variable with no persistence. If the backend process restarts mid-session, the specialist is silently deactivated and the chat reverts to base behavior with no notification to the frontend.

**Empty `tools` list means unrestricted, not locked down.** `filter_tools` returns all tools when `specialist.tools` is empty. A newly created specialist that skips the tools step can therefore use every tool. This is the open-by-default design choice — not a bug — but it means the absence of a `tools` list should not be read as "no tools allowed."

**Suggestion uses substring matching across role words.** The keyword extraction for `suggest_specialist` splits the role description on whitespace and checks each word individually. Short or common words in a role description (e.g. "a", "the", "and") will match almost any user message, producing false positives. In practice this is mitigated by the specialist name and source paths being checked first, but a role like "A general assistant for everything" would trigger a suggestion on nearly every message.

**`/api/specialists/activate/{id}` route ordering.** The `POST /api/specialists/activate/{id}` route is registered after `POST /api/specialists` in the router. FastAPI resolves this correctly because `activate` is a fixed path segment, not a parameter — but adding any future `POST /api/specialists/{action}` pattern would collide with the existing `POST /api/specialists/{spec_id}` update route if the intent were a PUT-style update via POST.

**File deletion is permanent, not trashed.** `delete_specialist_file()` calls `unlink()` directly — there is no soft-delete or trash mechanism for individual knowledge files, unlike specialist JSON definitions which are moved to `.trash/`. A user who accidentally deletes a knowledge file cannot recover it through the application.

**Knowledge files stored under `agents/`, not `memory/`.** The original design called for `memory/specialists/{id}/` to keep all user knowledge under the `memory/` tree (Obsidian-compatible, rebuildable). The actual implementation uses `agents/{id}/` instead. This means specialist knowledge files are not visible in Obsidian if the user points Obsidian at `memory/`, and they are not covered by the source-of-truth doctrine that positions `memory/` as the canonical store. This is a known trade-off favoring co-location over doctrine compliance.

**URL ingest creates a duplicate file.** `ingest_specialist_url` first ingests the URL into `memory/knowledge/` via the standard pipeline, then copies the result into `agents/{id}/`. This means every URL-ingested file exists in two locations. The copy in `memory/knowledge/` is discoverable by base Jarvis retrieval, which may or may not be desired.

**Specialist name (and ID) cannot be changed after creation.** The edit wizard makes the Name field read-only because the specialist ID is derived by slugifying the name at creation time. Renaming would require creating a new specialist, migrating its knowledge files, and deleting the old one. The `PUT /api/specialists/{id}` endpoint accepts a `name` field in the payload, but changing it would create a mismatch between the ID (filename) and the display name.

**Wizard examples field is not exposed in the UI.** `SpecialistWizard.vue` initializes `form.examples` as an empty array but has no step for adding example exchanges. Examples can only be provided by editing the JSON file directly or via `PUT /api/specialists/{id}` after creation.
