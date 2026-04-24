# Step 26 — Smart Connect Backfill, Quality Loop & Guardrails

> **Goal**: Turn the Smart Connect engine built in Step 25 into a
> measurable, trustworthy system. Four areas: (1) backfill existing notes
> so the whole vault benefits, (2) add a quality feedback loop so we can
> see which signals fire and whether users accept or dismiss, (3) guardrails
> on the alias matcher so short/generic aliases don't pollute suggestions,
> and (4) a score breakdown users can inspect when a suggestion looks wrong.

**Status**: ⬜ Not started  
**Depends on**: Step 25 (Smart Connect, all 6 PRs)  
**Effort**: ~2 days backend + 0.5 day frontend

---

## Why this step exists

Step 25 solved the hard problems: `connect_note()` exists, the graph grows
incrementally, dismissed pairs are remembered, and the UI shows suggestions.

Three problems remain:

1. **Existing notes have no `suggested_related`.** Every note imported before
   Step 25 is a frontier that Smart Connect has never touched. Without
   backfill, the vault looks linked for new notes and silent for old ones.

2. **We don't know if the signals are any good.** We ship BM25 + embeddings
   + alias as input weights but have zero production data on which method
   actually drives acceptance vs rejection. We are flying blind.

3. **Short and generic aliases are a foot-gun.** Aliases like `AI`, `API`,
   `memory`, `graph`, `model` will produce near-universal matches and
   destroy precision. We need a guard before users hit this at scale.

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
  "dry_run": false
}
```

Behaviour:

- Fetch all note paths from SQLite (or only semantic orphans if `only_orphans=true`).
- Process in batches of `batch_size`. Each batch is a sequential iteration — no
  parallelism to avoid read/write contention on the graph JSON.
- Per note: call `connect_note()` exactly as ingest does. Skip notes that
  already have `suggested_related` **and** are not orphans (idempotent
  re-entry is safe but wasteful).
- Stream progress via `text/event-stream` (SSE): one line per completed batch:
  `{"done": 50, "total": 312, "orphans_found": 4}`.
- `dry_run=true` runs the full pipeline but does **not** write frontmatter or
  emit graph edges. Returns the same SSE stream with a `dry_run: true` flag.

New Pydantic schema (`schemas.py`):

```python
class BackfillRequest(BaseModel):
    mode: Literal["fast", "aggressive"] = "fast"
    batch_size: int = Field(50, ge=1, le=500)
    only_orphans: bool = False
    dry_run: bool = False

class BackfillProgress(BaseModel):
    done: int
    total: int
    orphans_found: int
    dry_run: bool
```

### 2. Stats endpoint

New endpoint:

```
GET /api/connections/stats
```

Returns:

```json
{
  "notes_total": 1240,
  "notes_with_suggestions": 312,
  "notes_with_related": 84,
  "semantic_orphans": 41,
  "suggestions_total": 876,
  "dismissed_total": 93,
  "method_breakdown": {
    "bm25": 540,
    "note_emb": 410,
    "chunk_emb": 201,
    "alias": 88
  }
}
```

All computed from:
- `notes` table (path count)
- File scan of `suggested_related` frontmatter fields
- `dismissed_suggestions` table
- `alias_index` table for method stats

No extra tables — pure query-time aggregation against existing data.

### 3. Score breakdown in `SuggestedLink`

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
```

`suggested_at` is an ISO-8601 UTC timestamp set in `_finalise()`.

`score_breakdown` is a `{method: raw_contribution}` dict written when at
least two signals fired:

```yaml
suggested_related:
  - path: projects/retrieval.md
    confidence: 0.82
    methods: [bm25, note_emb, alias]
    tier: strong
    evidence: "hybrid retrieval"
    suggested_at: "2026-04-27T14:32:00Z"
    score_breakdown:
      bm25: 0.31
      note_emb: 0.27
      alias: 0.18
```

Individual contributions MUST sum to `confidence` (within floating-point
tolerance). This is verified in the unit tests. Do NOT write a breakdown
when only one method fired — it is redundant and noisy.

### 4. Alias guardrails

Add validation in `alias_index.upsert_note_aliases()`:

**4a. Minimum length**

Do not register any phrase below 4 characters (already spec'd in Step 25,
now enforced).

**4b. Stopword list**

Maintain a module-level set `_ALIAS_STOPWORDS` of technical stopwords that
are too broad to be meaningful aliases:

```python
_ALIAS_STOPWORDS = {
    "ai", "api", "ml", "nlp", "llm", "rag", "etl",
    "memory", "graph", "model", "data", "note", "file",
    "notes", "docs", "doc", "page", "item", "record",
    "list", "plan", "task", "work", "project",
}
```

Phrases that consist entirely of stopwords are silently skipped.

A phrase like `"AI assistant"` (contains one stopword) is fine; `"AI"` alone
is not.

**4c. Frequency cap**

After upsert, compute:

```sql
SELECT COUNT(DISTINCT note_path)
FROM alias_index
WHERE phrase_norm = ?
```

If the count exceeds 5% of the total note count (minimum threshold: 10
notes), log a warning and do NOT add the phrase to the index. The phrase
is too ubiquitous to discriminate between notes.

Frequency cap is computed lazily (only on upsert of a new phrase, not on
every re-index). Cache the total note count per call to avoid N+1 queries.

**4d. `weak_aliases` frontmatter key**

Honour a new optional frontmatter field:

```yaml
aliases:
  - "hybrid retrieval pipeline"     # strong — match alone is sufficient
weak_aliases:
  - "retrieval"                      # weak — only count if another method also fires
```

`weak_aliases` are indexed with `kind = 'weak_alias'`. In
`connection_service._alias_signal()`, hits on `weak_alias` phrases
contribute **0.35** instead of **1.0** to the per-candidate alias score.
They can push a borderline candidate over the floor but cannot
independently exceed `normal` tier.

### 5. Retrieval guard — `suggested_related` influence on retrieval

Currently `suggested_related` edges (weight 0.35) are added to the graph
by `fast_ingest` and are therefore visible to the retrieval scorer.

This is intentional but needs an explicit rule:

**Rule**: `suggested_related` edges contribute at most
`min(weight, 0.35)` to a node's graph score during retrieval. They do
not count as "meaningful semantic edges" for the purpose of orphan
classification (i.e. a note with only `suggested_related` edges is still
a semantic orphan). This rule is enforced in `graph_service/queries.py`
by keeping `suggested_related` in the `ignore_edge_types` set of
`find_semantic_orphans()`.

`source` and `batch` edges (types `derived_from`, `same_batch`) also
must NOT rescue a note from semantic orphan status on their own, because
they indicate provenance, not semantic relatedness. Add both to the
ignore set.

Update `find_semantic_orphans()` default `ignore_edge_types`:

```python
DEFAULT_IGNORE_EDGE_TYPES = frozenset({
    "tagged", "part_of", "temporal",
    "derived_from", "same_batch",      # provenance — not semantic
    "suggested_related",               # unconfirmed — not semantic
})
```

### 6. "Promote all strong" UI action

Add to `SuggestionsPanel.vue`:

A single header-level button **"Keep all (N)"** which:
- is visible only when `suggestions.filter(s => s.confidence >= 0.80).length >= 2`
- is capped at a maximum of 5 strong items (do not show if more than 5 to
  avoid bulk errors that are hard to undo)
- calls `promoteSuggestion()` for each item sequentially (not parallel —
  makes each write visible in the note)
- after all have been promoted, emits `changed` once and shows one
  aggregated snackbar: `"Linked 3 notes"`

### 7. Backfill UI in Settings

Add to `frontend/app/pages/settings.vue` (or the Memory settings sub-panel
if one exists — check existing structure):

```
Smart Connect
  [Run Smart Connect on all notes]       → POST /api/connections/backfill
  [Run only on semantic orphans]         → POST /api/connections/backfill {"only_orphans": true}
  [Dry-run preview]                      → POST /api/connections/backfill {"dry_run": true}
```

Progress bar fed by the SSE stream. Stats panel below, fed by
`GET /api/connections/stats` (auto-refreshes after backfill completes).

---

## API surface

All new or extended under `/api/connections/`:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/connections/backfill` | Run `connect_note()` across all / orphan notes, SSE progress |
| `GET`  | `/api/connections/stats`    | Aggregated workspace-level Smart Connect metrics |

`SuggestedLink` schema extended with `score_breakdown` and `suggested_at` (backwards-compatible, both optional).

---

## Tests

Backend (`backend/tests/`):

- `test_connection_service_backfill.py`
  - backfill processes all notes without exception
  - dry-run does not write frontmatter
  - only-orphans flag skips already-connected notes
  - batch_size respected (mock note list, assert call count)

- `test_alias_guardrails.py`
  - phrases < 4 chars are rejected
  - stopword-only phrases are rejected
  - `"AI"` rejected, `"AI assistant"` accepted
  - frequency cap: phrase stored by 10+ notes is blocked on upsert
  - `weak_alias` kind indexed with correct kind value
  - `weak_alias` hit contributes 0.35 to alias score, not 1.0

- `test_connection_stats.py`
  - returns correct `notes_total`, `semantic_orphans`, `dismissed_total`
  - `method_breakdown` keys match methods in `_merge_candidates`

- `test_suggest_breakdown.py`
  - `score_breakdown` dict sums to `confidence` (±0.001)
  - `score_breakdown` absent when only one method fired
  - `suggested_at` is a valid ISO-8601 timestamp

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

Frontend (`frontend/tests/components/`):

- `SuggestionsPanel.test.ts` (extend existing):
  - "Keep all" button hidden when < 2 strong suggestions
  - "Keep all" button calls `promote` for each strong item in sequence
  - `score_breakdown` tooltip content renders on hover

---

## Definition of Done

1. `POST /api/connections/backfill` exists, streams SSE progress, respects `dry_run` and `only_orphans`.
2. `GET /api/connections/stats` returns the metrics JSON above.
3. `SuggestedLink` carries `score_breakdown` and `suggested_at`; existing frontmatter without these fields parses without error.
4. Alias guardrails: min-length, stopword list, frequency cap, `weak_aliases` support — all tested.
5. `find_semantic_orphans()` default `ignore_edge_types` includes `derived_from`, `same_batch`, `suggested_related`.
6. "Keep all strong" button in `SuggestionsPanel` (≥ 2 strong, capped at 5).
7. Backfill UI in Settings with progress bar and stats panel.
8. All tests above pass. Polish slug/alias regression suite added.
9. `docs/.registry.json` updated; this spec linked from `docs/steps/step-00-index.md`.

---

## Out of scope

- Accept/dismiss analytics persisted to DB — `dismissed_suggestions` already records dismissals; full acceptance history (recording every `promote`) is deferred to a dedicated analytics step.
- AI re-rank (`smart_connect_rerank`) — remains opt-in, deferred from Step 25.
- `suggested_at` + `method_signature` reraise logic ("show again if confidence jumped 0.25") — too complex for MVP; dismissed pairs stay dismissed.
- HNSW / ANN index — not needed at current scale.
- Cross-workspace suggestions.
