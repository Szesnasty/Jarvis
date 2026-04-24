# Step 26 — Smart Connect Backfill, Quality Loop & Guardrails

> **Goal**: Turn the Smart Connect engine built in Step 25 into a
> measurable, trustworthy system. Five areas: (1) backfill so the whole
> vault benefits, (2) versioning so future improvements re-run cleanly,
> (3) guardrails on the alias matcher, (4) a real feedback loop with
> promote/dismiss event log, and (5) score breakdown users can inspect.

**Status**: ⬜ Not started
**Depends on**: Step 25 (Smart Connect, all 6 PRs)
**Effort**: ~2 days backend + 0.5 day frontend

---

## Why this step exists

Step 25 solved the hard problems: `connect_note()` exists, the graph grows
incrementally, dismissed pairs are remembered, and the UI shows suggestions.

What's still missing:

1. **Existing notes have no `suggested_related`.** Every note imported before
   Step 25 is invisible to Smart Connect.
2. **No way to re-run Smart Connect after algorithm changes.** Without
   versioning, "skip if already has suggestions" locks old notes to v1
   forever.
3. **No production data on signal quality.** We ship BM25 + embeddings +
   alias as input weights but cannot see which method drives acceptance.
4. **Short and generic aliases will spam suggestions** (`AI`, `API`,
   `memory`, `graph`).
5. **No way to inspect why a suggestion was made.** Trust requires
   explainability.

---

## Changes

### 1. Backfill endpoint

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
- Process in batches of `batch_size`. Each batch is sequential — no
  parallelism (avoid graph JSON write contention).
- Per note: call `connect_note()` exactly as ingest does.
- **Skip rules** (note is skipped when ALL of these are true):
  - `force=false`
  - `note.frontmatter.smart_connect.version >= CURRENT_SMART_CONNECT_VERSION`
  - `suggested_related` exists in frontmatter
  - note is not a semantic orphan
- `dry_run=true` is read-only (see §3 below).
- `min_confidence` (optional float) filters which suggestions are written;
  helpful for conservative bulk runs.

**SSE transport**: The endpoint streams `text/event-stream` from a `POST`
request. Native browser `EventSource` does NOT support `POST`, so the
frontend MUST consume the stream via `fetch()` + `ReadableStream`, not
`EventSource`. This is documented as a frontend implementation rule.

Stream payload per batch:

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

New Pydantic schema (`schemas.py`):

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

### 2. Smart Connect versioning

Add a module-level constant in `connection_service.py`:

```python
CURRENT_SMART_CONNECT_VERSION = 2
```

When `connect_note()` writes frontmatter, also write:

```yaml
smart_connect:
  version: 2
  last_run_at: "2026-04-27T14:32:00Z"
  last_mode: fast
```

Each `SuggestedLink` also carries `suggested_by: smart_connect_v2`.

Bumping `CURRENT_SMART_CONNECT_VERSION` causes the next backfill to
revisit all notes that have a lower version — without `force`.

This was the missing piece to make backfill safe to re-run after future
algorithm tweaks.

### 3. Dry-run as strict read-only

To make `dry_run=true` actually testable and safe, refactor the orchestrator:

```python
def generate_suggestions(note_path: str) -> list[SuggestedLink]:
    """Pure: reads indexes, returns candidates. No writes."""

def apply_suggestions(note_path: str, suggestions: list[SuggestedLink]) -> None:
    """Writes frontmatter, emits graph edges, updates indexes."""

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

Tested explicitly (see Tests).

### 4. Score breakdown in `SuggestedLink`

Extend the Pydantic model in `schemas.py`:

```python
class SuggestedLink(BaseModel):
    path: str
    confidence: float
    methods: list[str]
    tier: str
    evidence: str | None = None
    score_breakdown: dict[str, float] | None = None
    suggested_at: str | None = None
    suggested_by: str | None = None  # e.g. "smart_connect_v2"
```

`suggested_at` is an ISO-8601 UTC timestamp set in `_finalise()`.

`score_breakdown` is a `{method: normalized_contribution}` dict written
when at least two signals fired. Stored values are **final normalized
contributions after caps, floors, and weights** — they sum to
`confidence` (±0.001). They are NOT raw internal scores. If we later
need raw debug data, we add a separate `debug_score_raw` field; out of
scope here.

```yaml
suggested_related:
  - path: projects/retrieval.md
    confidence: 0.82
    methods: [bm25, note_emb, alias]
    tier: strong
    evidence: "hybrid retrieval"
    suggested_at: "2026-04-27T14:32:00Z"
    suggested_by: smart_connect_v2
    score_breakdown:
      bm25: 0.31
      note_emb: 0.27
      alias: 0.24
```

Do NOT write `score_breakdown` when only one method fired.

### 5. Alias guardrails

Add validation in `alias_index.upsert_note_aliases()`:

**5a. Minimum length + short-acronym allowlist**

Reject phrases below 4 characters, EXCEPT those in an allowlist of
common technical acronyms:

```python
_ALIAS_SHORT_ALLOWLIST = {
    "aws", "jwt", "sql", "css", "gpu", "cpu",
    "ui", "ux", "s3", "k8s", "ci", "cd",
}
```

This is a deliberate trade-off: most short tokens are noise, but a few
technical acronyms are highly discriminative. The allowlist is small,
explicit, and easy to extend.

**5b. Stopword list**

Module-level set of broad terms that are too generic to discriminate:

```python
_ALIAS_STOPWORDS = {
    "ai", "api", "ml", "nlp", "llm", "rag", "etl",
    "memory", "graph", "model", "data", "note", "file",
    "notes", "docs", "doc", "page", "item", "record",
    "list", "plan", "task", "work", "project",
}
```

Phrases consisting **entirely** of stopwords are rejected.
`"AI assistant"` (one stopword + one content word) is fine; `"AI"` alone
is not.

**5c. Frequency cap (computed BEFORE insert)**

```python
threshold = max(10, ceil(total_notes * 0.05))
existing_count = count_distinct_notes_for_phrase(phrase_norm)

if existing_count >= threshold and note_path not already indexed_for_phrase:
    block phrase  # do not insert
else:
    insert/update
```

Required SQL indexes (add migration):

```sql
CREATE INDEX IF NOT EXISTS idx_alias_index_phrase_norm
  ON alias_index(phrase_norm);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alias_index_phrase_note_kind
  ON alias_index(phrase_norm, note_path, kind);
```

`total_notes` cached per backfill call to avoid N+1 queries.

**5d. `weak_aliases` frontmatter key**

Honour a new optional frontmatter field:

```yaml
aliases:
  - "hybrid retrieval pipeline"     # strong
weak_aliases:
  - "retrieval"                      # weak
```

`weak_aliases` are indexed with `kind = 'weak_alias'`.

**Strict rule (tightened from initial spec)**:

> A `weak_alias` hit alone MUST NOT emit a suggestion. It only contributes
> to candidates that already have at least one non-alias signal
> (`bm25`, `note_emb`, or `chunk_emb`).

When the candidate qualifies, a `weak_alias` hit contributes **0.35** to
the per-candidate alias score (vs **1.0** for a normal alias). It cannot
push a candidate above `normal` tier on its own.

### 6. Retrieval guard — provenance and unconfirmed edges

Step 25 added `derived_from`, `same_batch`, and `suggested_related` edges.
None of these are semantic relations:

- `derived_from` / `same_batch` = provenance, not meaning
- `suggested_related` = unconfirmed candidate, not user-validated

Update `find_semantic_orphans()` default `ignore_edge_types`:

```python
DEFAULT_IGNORE_EDGE_TYPES = frozenset({
    "tagged", "part_of", "temporal",
    "derived_from", "same_batch",      # provenance — not semantic
    "suggested_related",               # unconfirmed — not semantic
})
```

Retrieval scorer (`graph_service/queries.py`): `suggested_related` edges
contribute at most `min(weight, 0.35)` to a node's graph score. They
provide a soft signal but do not dominate scoring before user review.

### 7. Stats endpoint

```
GET /api/connections/stats
```

Returns:

```json
{
  "notes_total": 1240,
  "notes_with_suggestions": 312,
  "notes_with_related": 84,
  "semantic_orphans_total": 41,
  "semantic_orphans_with_suggestions": 28,
  "semantic_orphans_without_suggestions": 13,
  "suggestions_total": 876,
  "method_breakdown": {
    "bm25": 540,
    "note_emb": 410,
    "chunk_emb": 201,
    "alias": 88,
    "weak_alias": 22
  },
  "events": {
    "promoted_total": 184,
    "dismissed_total": 93,
    "acceptance_rate": 0.66,
    "promoted_by_method": {
      "alias": 72, "chunk_emb": 61, "bm25": 88
    },
    "dismissed_by_method": {
      "bm25": 40, "weak_alias": 18
    }
  },
  "alias_index": {
    "phrases_total": 1832,
    "weak_phrases_total": 244,
    "blocked_phrases_total": 6
  }
}
```

**Computation rules** (this was a bug in the first draft):

- `method_breakdown` is computed by **scanning `suggested_related[].methods`
  in note frontmatter**, NOT by reading `alias_index`.
- `events.*` is computed from `connection_events` (see §8).
- `alias_index.*` is for index health only — never mixed with method stats.

### 8. Promote/dismiss event log

Without recording promote events we cannot compute acceptance rate or
"which methods produced accepted suggestions". Step 25 only persisted
dismissals.

Add a single SQLite table (cheap, unlocks the whole quality loop):

```sql
CREATE TABLE IF NOT EXISTS connection_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,        -- 'promote' | 'dismiss' | 'backfill_suggested'
    note_path TEXT NOT NULL,
    target_path TEXT,
    confidence REAL,
    methods_json TEXT,                -- JSON array
    tier TEXT,
    smart_connect_version INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_connection_events_type_created
  ON connection_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_connection_events_note
  ON connection_events(note_path);
```

Write events on:
- `POST /api/connections/promote` → `event_type = 'promote'`
- `POST /api/connections/dismiss` → `event_type = 'dismiss'`
  (in addition to keeping the existing `dismissed_suggestions` table —
  it stays the source of truth for "do not re-suggest")
- Each backfill batch → `event_type = 'backfill_suggested'`, one row per
  emitted suggestion (subject to a sane cap, e.g. skip if same
  `(note_path, target_path, smart_connect_version)` already logged today)

The existing `dismissed_suggestions` table remains as the dedup source
for the suggestion pipeline. `connection_events` is purely analytical.

### 9. "Promote all strong" UI action

Add to `SuggestionsPanel.vue`:

A header-level button **"Keep all (N)"** which:
- visible only when `suggestions.filter(s => s.confidence >= 0.80).length >= 2`
- capped at maximum 5 strong items (button hidden if more than 5)
- when `N > 3`: shows a small inline confirmation (`"Keep N suggested links?
  [Cancel] [Keep all]"`) before promoting. For N = 2 or 3: promote
  immediately.
- calls `promoteSuggestion()` for each item sequentially
- after all promoted, emits `changed` once and shows one snackbar
  `"Linked N notes"`

### 10. Backfill UI in Settings

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

Progress bar fed by the SSE stream (consumed via `fetch()` +
`ReadableStream`). Live counters: `done/total`, `suggestions_added`,
`notes_changed`, `skipped`. Stats panel below auto-refreshes after
backfill completes.

---

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/connections/backfill` | Backfill (SSE progress over fetch stream) |
| `GET`  | `/api/connections/stats`    | Workspace-level Smart Connect metrics |

Existing `POST /promote` and `POST /dismiss` extended to write to
`connection_events`.

`SuggestedLink` schema extended with `score_breakdown`, `suggested_at`,
`suggested_by` (all optional, backwards-compatible).

---

## Tests

Backend (`backend/tests/`):

- `test_connection_service_backfill.py`
  - backfill processes all notes without exception
  - `dry_run=true` does NOT modify frontmatter, graph JSON, `alias_index`,
    `dismissed_suggestions`, `connection_events`
  - `only_orphans=true` skips already-connected notes
  - `batch_size` respected (mock note list, assert batch count)
  - `force=true` re-processes notes at current version
  - **versioning**: note with `smart_connect.version < CURRENT` is processed;
    note with `smart_connect.version >= CURRENT` is skipped (unless `force`)

- `test_alias_guardrails.py`
  - phrases < 4 chars rejected
  - phrases in `_ALIAS_SHORT_ALLOWLIST` accepted (e.g. `"jwt"`, `"aws"`)
  - stopword-only phrases rejected (`"AI"`, `"memory"`)
  - mixed phrase accepted (`"AI assistant"`)
  - frequency cap blocks new insert when phrase already in ≥ 5% of notes
  - cap check happens BEFORE insert (verify by inspecting DB after attempt)
  - `weak_alias` indexed with `kind='weak_alias'`
  - `weak_alias` alone produces NO suggestion
  - `weak_alias + bm25` produces a suggestion
  - `weak_alias` cannot reach `strong` tier alone
  - `weak_alias` contribution = 0.35, normal alias = 1.0

- `test_connection_stats.py`
  - returns correct totals
  - `method_breakdown` counts come from `suggested_related[].methods`,
    NOT from `alias_index`
  - `semantic_orphans_with_suggestions` + `_without_suggestions` ==
    `semantic_orphans_total`
  - `events.acceptance_rate` = promoted / (promoted + dismissed)

- `test_connection_events.py`
  - promote writes one row with `event_type='promote'` and methods
  - dismiss writes one row with `event_type='dismiss'`
  - backfill writes `backfill_suggested` rows per emitted suggestion
  - aggregations group by method correctly

- `test_suggest_breakdown.py`
  - `score_breakdown` dict sums to `confidence` (±0.001)
  - `score_breakdown` absent when only one method fired
  - `suggested_at` is a valid ISO-8601 UTC timestamp
  - `suggested_by` equals `"smart_connect_v{CURRENT_SMART_CONNECT_VERSION}"`

- `test_pl_slug_alias.py` (Polish regression)
  - slugify: `"Łódź → lodz"`, `"Zażółć gęślą jaźń → zazolc-gesla-jazn"`,
    `"Świnoujście → swinoujscie"`, `"Michał → michal"`, `"żółć → zolc"`
  - alias scan: `"wyszukiwanie hybrydowe"` matches alias
    `"Wyszukiwanie hybrydowe"`; `"Łódź"` matches normalised `"lodz"`

- Extended `test_connection_service_orphan.py`:
  - note with only `derived_from` edge is still a semantic orphan
  - note with only `same_batch` edge is still a semantic orphan
  - note with only `suggested_related` edge is still a semantic orphan
  - note with a `related` edge (user-confirmed) is NOT a semantic orphan
  - retrieval scoring caps `suggested_related` contribution at 0.35

Frontend (`frontend/tests/components/`):

- `SuggestionsPanel.test.ts` (extend):
  - "Keep all" button hidden when < 2 strong
  - "Keep all" button hidden when > 5 strong
  - N = 2 or 3: promotes immediately without confirmation
  - N = 4 or 5: shows inline confirmation, cancellable
  - calls `promote` for each strong item in sequence
  - `score_breakdown` tooltip renders on hover

- `BackfillPanel.test.ts` (new):
  - dry-run button calls endpoint with `dry_run: true`
  - SSE progress is rendered from streamed JSON lines
  - stats panel refetches after stream ends

---

## Definition of Done

1. `POST /api/connections/backfill` exists; respects `dry_run`,
   `only_orphans`, `force`, `min_confidence`; streams SSE consumed via
   `fetch()` + `ReadableStream` on the frontend.
2. `GET /api/connections/stats` returns the metrics JSON above.
   `method_breakdown` is computed from frontmatter, NOT from `alias_index`.
3. `SuggestedLink` carries `score_breakdown`, `suggested_at`,
   `suggested_by`. Existing frontmatter without these parses without error.
4. `connect_note()` writes `smart_connect.version =
   CURRENT_SMART_CONNECT_VERSION` to the note's frontmatter.
5. Dry-run is strictly read-only across all backing stores (verified by tests).
6. Alias guardrails: min-length, short-acronym allowlist, stopword set,
   pre-insert frequency cap, `weak_aliases` semantics.
7. `connection_events` table exists with promote/dismiss writes wired into
   existing endpoints.
8. `find_semantic_orphans()` default `ignore_edge_types` includes
   `derived_from`, `same_batch`, `suggested_related`.
9. Retrieval scorer caps `suggested_related` edge contribution at 0.35.
10. "Keep all strong" button (≥ 2, capped at 5, confirmation when N > 3).
11. Backfill UI in Settings with progress + stats panel + dry-run warning.
12. All tests above pass. Polish slug/alias regression suite added.
13. `docs/.registry.json` updated; spec linked from
    `docs/steps/step-00-index.md`.

---

## Out of scope

- AI re-rank (`smart_connect_rerank`) — opt-in, deferred from Step 25.
- Show-again-if-confidence-jumped logic — too complex; dismissed pairs
  stay dismissed.
- HNSW / ANN index — not needed at current scale.
- Cross-workspace suggestions.
- Per-suggestion full debug breakdown (`debug_score_raw`) — only the
  normalized `score_breakdown` is in scope here.
- Auto-blocking of phrases that LATER cross the frequency cap (today's
  rule blocks new inserts only; cleanup is manual).
