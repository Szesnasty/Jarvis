# Step 26a — Smart Connect Backfill & Versioning

> **Goal**: Run Smart Connect on every existing note (not just new ones),
> with versioned skip-logic so re-runs after algorithm changes work cleanly,
> and a strict dry-run mode that is safe by construction.

**Status**: ⬜ Not started
**Depends on**: Step 25 (Smart Connect, all 6 PRs)
**Effort**: ~1 day backend

---

## Why this step exists

Step 25 connects notes at ingest time. Every note imported before Step 25
has no `suggested_related` — it was never touched by Smart Connect. Without
backfill, the vault is split: new notes are linked, old notes are silent.

A second problem: after this or future steps improve the scoring algorithm,
backfill needs to know which notes were processed at an older version and
should be re-visited. Without a version field, "skip if already has
suggestions" is permanent and wrong.

---

## Changes

### 1. Smart Connect versioning

Add to `connection_service.py`:

```python
CURRENT_SMART_CONNECT_VERSION = 2
```

When `connect_note()` writes frontmatter, add:

```yaml
smart_connect:
  version: 2
  last_run_at: "2026-04-27T14:32:00Z"
  last_mode: fast
```

Each `SuggestedLink` carries `suggested_by: smart_connect_v2`.

Bumping `CURRENT_SMART_CONNECT_VERSION` causes the next backfill to
re-visit notes at a lower version without `force=true`.

### 2. Dry-run as strict read-only

Refactor the orchestrator to separate reads from writes:

```python
def generate_suggestions(note_path: str) -> list[SuggestedLink]:
    """Pure read: queries indexes, returns candidates. No writes."""

def apply_suggestions(note_path: str, suggestions: list[SuggestedLink]) -> None:
    """Write: frontmatter, graph edges, version stamp."""

def connect_note(note_path: str, *, dry_run: bool = False) -> list[SuggestedLink]:
    suggestions = generate_suggestions(note_path)
    if not dry_run:
        apply_suggestions(note_path, suggestions)
    return suggestions
```

**Strict definition of `dry_run=true`**:

> Produces candidate suggestions and progress events but does NOT mutate:
> Markdown/frontmatter, graph JSON, `alias_index`, `dismissed_suggestions`,
> `connection_events`, `related`, or `suggested_related`. May read existing
> indexes. Must NOT lazily create missing embeddings.

### 3. Backfill endpoint

New endpoint in `routers/connections.py`:

```
POST /api/connections/backfill
```

Body (all optional — defaults shown):

```json
{
  "mode": "fast",
  "batch_size": 50,
  "only_orphans": false,
  "dry_run": false,
  "force": false,
  "min_confidence": null
}
```

Behaviour:

- Fetch all note paths from SQLite (or only semantic orphans if `only_orphans=true`).
- Process in batches of `batch_size`. Strictly sequential within a batch —
  no async parallelism to avoid graph JSON write contention.
- Per note: call `connect_note(dry_run=dry_run, min_confidence=min_confidence)`.
- **Skip a note when ALL of these are true** (treated as one atomic check):
  - `force=false`
  - `note.frontmatter.smart_connect.version >= CURRENT_SMART_CONNECT_VERSION`
  - `suggested_related` key exists in frontmatter
  - note is not a semantic orphan
- `min_confidence` (optional float) filters which suggestions are written;
  useful for conservative bulk runs without changing the scoring logic.

**SSE transport**

The endpoint returns `Content-Type: text/event-stream` from a `POST`
request. Native browser `EventSource` only supports `GET`, so the frontend
MUST consume this stream via `fetch()` + `ReadableStream`, not `EventSource`.
This is a hard implementation rule — document it in the composable.

Stream payload (one JSON object per completed batch, newline-delimited):

```json
{
  "done": 50,
  "total": 312,
  "suggestions_added": 124,
  "notes_changed": 37,
  "skipped": 13,
  "orphans_found": 4,
  "dry_run": false
}
```

New schemas in `schemas.py`:

```python
class BackfillRequest(BaseModel):
    mode: Literal["fast", "aggressive"] = "fast"
    batch_size: int = Field(50, ge=1, le=500)
    only_orphans: bool = False
    dry_run: bool = False
    force: bool = False
    min_confidence: float | None = Field(None, ge=0.0, le=1.0)

class BackfillProgress(BaseModel):
    done: int
    total: int
    suggestions_added: int
    notes_changed: int
    skipped: int
    orphans_found: int
    dry_run: bool
```

### 4. Backfill UI in Settings

In `frontend/app/pages/settings.vue` (or its Memory sub-panel):

```
Smart Connect
  [Run Smart Connect on all notes]   → POST /api/connections/backfill
  [Run only on semantic orphans]     → POST {"only_orphans": true}
  [Dry-run preview]                  → POST {"dry_run": true}

  Warning shown above "Run on all notes":
  > This may add suggested_related to many notes' frontmatter.
  > Run dry-run first to preview the impact.
```

Progress bar driven by the SSE stream via `fetch()` + `ReadableStream`.
Live counters: `done/total`, `suggestions_added`, `notes_changed`, `skipped`.
Stats panel below auto-refreshes after stream closes.

---

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/connections/backfill` | Backfill, SSE progress via fetch stream |

---

## Tests

Backend (`backend/tests/`):

- `test_connection_service_backfill.py`
  - backfill processes all notes in vault without exception
  - `dry_run=true` does NOT modify frontmatter, graph JSON, `alias_index`,
    `dismissed_suggestions`, `connection_events`
  - `only_orphans=true` skips notes that already have `related` edges
  - `batch_size=10` on 25-note mock — assert exactly 3 batch callbacks
  - `force=true` re-processes a note that is already at current version
  - note with `smart_connect.version < CURRENT` is processed on backfill
  - note with `smart_connect.version >= CURRENT` is skipped (force not set)
  - `min_confidence=0.8` — only strong suggestions written to frontmatter

Frontend (`frontend/tests/components/`):

- `BackfillPanel.test.ts`
  - dry-run button calls endpoint with `dry_run: true`
  - progress counters update from streamed JSON lines
  - final stats panel re-fetches after stream closes
  - warning message visible above "Run on all notes" button

---

## Definition of Done

1. `POST /api/connections/backfill` respects `dry_run`, `only_orphans`,
   `force`, `min_confidence`; streams newline-delimited JSON.
2. Frontend consumes stream via `fetch()` + `ReadableStream`.
3. `connect_note()` writes `smart_connect.version` to frontmatter on every
   non-dry-run call.
4. `generate_suggestions` / `apply_suggestions` split is in place.
5. Dry-run is strictly read-only (verified by tests above).
6. Backfill UI in Settings with progress bar, live counters, dry-run warning.
7. All tests above pass.
