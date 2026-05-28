# Step 29 — Unified Knowledge: Specialists as Views, Not Storage

> **Goal**: Eliminate the dual-inbox problem (`memory/` vs
> `agents/{id}/`). Every file the user uploads — through "Import" or
> through a specialist's upload card — lands in `memory/` as a
> first-class note. Specialists become a **profile + filter** over
> `memory/`, not a separate storage tier. Retrieval, graph, and Smart
> Connect work identically for all knowledge. The user never has to
> decide "where to put this file".

**Parent**: (new track — knowledge architecture cleanup)
**Status**: ✅ Done
**Depends on**: Step 09 (specialists), Step 19c (hybrid retrieval),
Step 22e (cross-source linking), Step 25 (Smart Connect).

---

## Why

### Today's pain

Knowledge that a specialist can see is split across **two stores
with different mechanics**:

1. `memory/` — Markdown, full retrieval stack (BM25 + embeddings +
   graph + Smart Connect), shared with Jarvis and all specialists.
2. `agents/{id}/` — raw files (PDF/MD/TXT/CSV/JSON), keyword-overlap
   only, 4 KB injection budget, invisible to anyone except that
   specialist. See
   [context_builder.py:_load_specialist_knowledge](../../backend/services/context_builder.py#L72-L106).

This produces three concrete UX failures:

- **"Where do I drop this PDF?"** is a forced decision at every
  upload. The user does not yet know which specialists will exist or
  what they'll want to share.
- **Inconsistent quality.** The same PDF in `memory/` is chunked,
  embedded, anchored, Smart-Connected, and graph-linked. In
  `agents/{id}/` it's a flat keyword grep against the file name + body.
- **No flow between stores.** Promoting `agents/{id}/foo.pdf` to
  workspace-wide visibility requires manual reimport.

### Violates project doctrine

`CLAUDE.md §1a` states: _"Source of truth = Markdown files in
`Jarvis/memory/`."_ The `agents/{id}/` files directory is the only
place in the system that breaks this rule — it stores user knowledge
outside `memory/` with no SQLite index and no graph entry. Step 29
brings specialists back in line with the doctrine.

### Anti-goal

We are **not** removing specialists. We are not removing
`agents/{id}.json`. The behavior layer (system prompt, style, rules,
examples, tools) stays where it is. What changes is the **knowledge
layer**.

---

## Design

### Doctrine

> **`memory/` is the only knowledge store. A specialist is a profile
> and a view over `memory/`, never a separate inbox.**

### Note frontmatter — new fields

Every note (existing or new) may carry:

```yaml
---
specialists: [health-guide, study-coach]   # optional, list of spec IDs
visibility: shared | private               # default: shared
---
```

- `specialists`: which specialists this note "belongs to" as
  curated knowledge. Empty/missing ⇒ general workspace knowledge.
- `visibility`:
  - `shared` (default) — visible to Jarvis + every specialist.
  - `private` — visible **only** to specialists listed in
    `specialists`. Hidden from Jarvis and from other specialists.

A note can belong to multiple specialists. A note with empty
`specialists` and `visibility: shared` behaves exactly like today's
generic `memory/` content.

### Specialist JSON — pruned

`agents/{id}.json` keeps **behavior only**:

```jsonc
{
  "id": "health-guide",
  "name": "Health Guide",
  "system_prompt": "...",
  "style": { ... },
  "rules": [ ... ],
  "tools": [ ... ],
  "examples": [ ... ],
  "icon": "🩺",
  "default_model": "claude-...",
  "scope": {                                // NEW — replaces "sources"
    "folders":   ["knowledge/health"],      // optional
    "tags":      ["sleep", "recovery"],     // optional
    "include_owned": true                   // include notes whose
                                            // frontmatter `specialists`
                                            // contains this id
  }
}
```

- `sources` (old field) is **deprecated** and migrated to
  `scope.folders` on first read (back-compat shim).
- `scope` is purely a **selector**. It never points to files outside
  `memory/`.

### Retrieval — single pipeline, scoped at the end

The retrieval pipeline does not change. After
`retrieval.retrieve(...)` returns candidates, the active specialist
applies a **single composable filter**:

```python
def visible_to(spec, note_fm, path) -> bool:
    if spec is None:
        return note_fm.get("visibility", "shared") == "shared"

    owned = spec["id"] in (note_fm.get("specialists") or [])
    if note_fm.get("visibility") == "private":
        return owned

    scope = spec.get("scope") or {}
    if not scope.get("folders") and not scope.get("tags") and not scope.get("include_owned"):
        return True  # unscoped specialist sees everything shared

    if scope.get("include_owned", True) and owned:
        return True
    if any(path.startswith(f.rstrip("/") + "/") for f in scope.get("folders", [])):
        return True
    if set(note_fm.get("tags") or []) & set(scope.get("tags") or []):
        return True
    return False
```

This **replaces** both:

- `_scope_results` in
  [context_builder.py:50-62](../../backend/services/context_builder.py#L50-L62)
  (folder-only filter).
- `_load_specialist_knowledge` in
  [context_builder.py:72-106](../../backend/services/context_builder.py#L72-L106)
  (parallel keyword-overlap loader). **Removed entirely.**

Specialist knowledge now flows through the same BM25 + embedding +
graph + reranker pipeline as everything else.

### Upload UX — one action, one decision

There are **two entry points**, both writing to `memory/`:

1. **Memory → Import** (existing). Default visibility: `shared`. No
   specialist assignment unless the user picks one in a dropdown.
2. **Specialist card → Upload** (existing). Defaults change:
   - Target path: `memory/knowledge/<spec-id>/<filename>` (created on
     demand).
   - Auto-injected frontmatter:
     `specialists: [<spec-id>]`, `visibility: private`.
   - **Single toggle** in the upload dialog: "Share with Jarvis and
     other specialists" → flips `visibility` to `shared`.

The user never picks "memory vs agents". They pick "who can see this".

### Reassigning ownership

A note's specialists/visibility can be edited from:

- The NoteViewer side panel (chips + dropdown).
- Bulk action in Memory: select notes → "Assign to specialist".
- Direct frontmatter edit (Obsidian-friendly).

No file moves. Reassignment = frontmatter rewrite.

---

## Migration

One-shot script: `scripts/migrate-specialist-files.py`.

For each `agents/{id}/` directory:

1. For each file `f`:
   - If `f.suffix in {.md, .txt}`: copy to
     `memory/knowledge/<id>/<filename>`, inject frontmatter
     `specialists: [<id>], visibility: private`.
   - If `f.suffix in {.pdf, .csv, .json}`: run the existing ingest
     pipeline (PDF section split for PDFs, etc.) targeting
     `memory/knowledge/<id>/`. Inject the same frontmatter on every
     produced note / index.
2. Index the new notes (SQLite + embeddings + graph). Standard
   ingest path.
3. Move the original `agents/{id}/<file>` to
   `.trash/agents-migration/<id>/<file>` (reversible).
4. Append a migration record to `app/migrations/29-specialists.json`
   mapping old path → new path(s).

For each `agents/{id}.json`:

- Rename `sources` → `scope.folders`.
- Add `scope.include_owned: true`.
- Drop nothing else.

Migration is **idempotent**: rerunning skips files already
present at the target path with matching frontmatter.

Rollback: restore from `.trash/agents-migration/` and revert
specialist JSONs from the migration record.

---

## Acceptance Criteria

1. Uploading a PDF from the Health Guide card produces a note at
   `memory/knowledge/health-guide/<slug>/index.md` (+ section files
   if split) with frontmatter
   `specialists: [health-guide], visibility: private`.
2. The same PDF is fully indexed: appears in SQLite `notes`, has
   embeddings, has graph nodes, participates in Smart Connect.
3. Health Guide active + asking a relevant question retrieves this
   PDF via the standard hybrid retrieval (BM25/embedding hit visible
   in the retrieval trace UI from Step 28a).
4. Jarvis (no specialist) asking the same question **does not** see
   the PDF (because `visibility: private`).
5. Toggling "Share with Jarvis" on the note flips frontmatter to
   `visibility: shared`. Jarvis now sees it on next query.
6. `_load_specialist_knowledge` is deleted. No code path reads
   `agents/{id}/*` for content.
7. Old `agents/{id}.json` files still load (back-compat shim maps
   `sources` → `scope.folders`).
8. Migration script run twice produces the same final state on
   disk and in SQLite (idempotency).
9. Retrieval trace shows specialist-owned notes with their normal
   signals (cosine / BM25 / graph), not a synthetic
   "specialist_knowledge" via.

---

## Changes — backend

| File | Change |
|------|--------|
| [services/specialist_service.py](../../backend/services/specialist_service.py) | Add `scope` field; back-compat shim mapping legacy `sources` → `scope.folders`. Drop `list_specialist_files`, `count_specialist_files`, file upload/delete handlers (or keep stubs returning empty for one release). |
| [services/context_builder.py](../../backend/services/context_builder.py) | Delete `_load_specialist_knowledge` and `_scope_results`. Add `_visible_to_specialist(spec, fm, path)`. Apply at the end of retrieval, before token-budget trim. |
| [services/retrieval.py](../../backend/services/retrieval.py) | Optional: pre-filter SQL/embedding candidates by `scope.folders` to save work. Filter again post-hoc for correctness (frontmatter is the truth). |
| [services/memory_service.py](../../backend/services/memory_service.py) | Surface `specialists` and `visibility` from frontmatter on `list_notes` (same shape as Step 28b added `document_type`/`parent`). |
| [routers/specialists.py](../../backend/routers/specialists.py) | Replace `POST/GET/DELETE /{spec_id}/files/...` with thin wrappers that call the existing memory upload pipeline targeting `memory/knowledge/<spec_id>/` and inject default frontmatter. Old endpoints stay one release for migration UI. |
| [routers/memory.py](../../backend/routers/memory.py) | New endpoints: `PATCH /notes/{path}/ownership` (set `specialists` + `visibility`); bulk variant. |
| [scripts/migrate-specialist-files.py](../../scripts) | New. Migration described above. |

## Changes — frontend

| File | Change |
|------|--------|
| `SpecialistCard.vue` / specialist files panel | "Files" tab calls memory listing filtered by `specialists: [<id>]`, not the old `/specialists/{id}/files` endpoint. Upload dialog gains "Share with Jarvis & other specialists" toggle. |
| `ImportDialog.vue` | Add optional "Assign to specialist" dropdown. |
| `NoteViewer.vue` | Side panel: edit `specialists` (multi-select chips) + `visibility` toggle. Emits `ownership-changed`. |
| `NoteList.vue` | Show a small badge on notes that belong to a specialist; filter chip "Owned by …". |
| `types/index.ts` | Add `specialists?: string[]; visibility?: 'shared' \| 'private'` to `NoteMetadata`. |

---

## Out of Scope

- Per-section ownership (every section inherits the parent's
  `specialists` / `visibility` for now).
- Group / team specialists.
- Visibility levels beyond `shared` / `private` (e.g. per-specialist
  whitelists). The schema is open for future extension but MVP ships
  with two states.
- Automatic specialist suggestion based on note content. Manual
  assignment only in MVP.
