# Step 26c — Smart Connect Quality Loop: Score Breakdown, Event Log & Stats

> **Goal**: Make Smart Connect measurable and explainable. Users can see why
> a suggestion was made, acceptance rate is tracked, and a stats endpoint
> shows which signals actually drive useful connections.

**Status**: ✅ Implemented
**Depends on**: Step 26a (versioning, `SuggestedLink` model), Step 26b (methods
list is clean after alias guardrails)
**Effort**: ~1 day backend + 0.5 day frontend

---

## Why this step exists

After 26a and 26b, Smart Connect reaches the whole vault and produces
cleaner suggestions. But there's still no answer to:

- "Why did Jarvis suggest this?"
- "Are suggestions being accepted or dismissed?"
- "Is `bm25` or `alias` actually driving value?"

Without event logging, the stats endpoint can only count current state; it
cannot show acceptance rate or method effectiveness. Without score breakdown
in the suggestion, users can't inspect or debug surprising links.

---

## Changes

### 1. Score breakdown in `SuggestedLink`

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
    suggested_by: str | None = None  # "smart_connect_v2"
```

`suggested_at` — ISO-8601 UTC timestamp set in `_finalise()`.

`score_breakdown` — `{method: contribution}` dict written when **at least
two signals fired**. Values are **final normalized contributions after
caps, floors, and weights** — they must sum to `confidence` (±0.001).
These are NOT raw internal scores. When only one method fires, omit the
field (redundant noise).

Example written to frontmatter:

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

### 2. Promote/dismiss event log

`dismissed_suggestions` (Step 25) records what not to re-suggest. But
without recording promote events, we cannot compute acceptance rate or
which methods drove accepted suggestions.

Add one SQLite table:

```sql
CREATE TABLE IF NOT EXISTS connection_events (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type             TEXT NOT NULL,   -- 'promote' | 'dismiss' | 'backfill_suggested'
    note_path              TEXT NOT NULL,
    target_path            TEXT,
    confidence             REAL,
    methods_json           TEXT,             -- JSON array, e.g. '["bm25","alias"]'
    tier                   TEXT,
    smart_connect_version  INTEGER,
    created_at             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_connection_events_type_created
  ON connection_events(event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_connection_events_note
  ON connection_events(note_path);
```

Write events:

- `POST /api/connections/promote` → one row `event_type='promote'`
- `POST /api/connections/dismiss` → one row `event_type='dismiss'`
  (the `dismissed_suggestions` table remains the authoritative dedup
  store for the pipeline — `connection_events` is analytics-only)
- Each backfill suggestion emitted → one row `event_type='backfill_suggested'`
  (deduplicated: skip if same `(note_path, target_path, smart_connect_version)`
  already logged today)

### 3. Stats endpoint

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

**Computation rules:**

- `method_breakdown` — scan `suggested_related[].methods` across note
  frontmatter. NOT from `alias_index`. This was a bug in the initial draft.
- `semantic_orphans_with_suggestions` / `_without_suggestions` — split by
  whether the orphan has at least one `suggested_related` entry.
- `events.*` — from `connection_events` table.
- `alias_index.*` — index health only; never mixed with method stats.
- `acceptance_rate` = `promoted_total / (promoted_total + dismissed_total)`.
  Returns `null` when denominator is 0.

### 4. "Promote all strong" UI action

Add to `SuggestionsPanel.vue`:

A header-level button **"Keep all (N)"** which:

- visible only when `suggestions.filter(s => s.confidence >= 0.80).length >= 2`
- hidden when that count exceeds 5 (too many to bulk-promote safely)
- **N ≤ 3**: promotes immediately without confirmation
- **N = 4 or 5**: shows a small inline confirmation before acting:
  `"Keep N suggested links? [Cancel] [Keep all]"`
- calls `promoteSuggestion()` for each item sequentially (not parallel —
  each write reaches the file before the next one starts)
- emits `changed` once after all promotions complete
- shows one aggregated snackbar: `"Linked N notes"`

### 5. "Why?" tooltip in SuggestionsPanel

When `score_breakdown` is present on a `SuggestedLink`, show a small info
icon next to the suggestion. On hover/click, show a tooltip:

```
Why this suggestion?
bm25     0.31
note_emb 0.27
alias    0.24
──────────────
total    0.82
```

No tooltip when `score_breakdown` is absent.

---

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/api/connections/stats` | Workspace-level quality metrics |

Existing `POST /promote` and `POST /dismiss` extended to write to
`connection_events` (no signature change).

`SuggestedLink` schema extended with `score_breakdown`, `suggested_at`,
`suggested_by` — all optional, fully backwards-compatible.

---

## Tests

Backend (`backend/tests/`):

- `test_suggest_breakdown.py`
  - `score_breakdown` sums to `confidence` (±0.001) when two or more
    signals fired
  - `score_breakdown` absent when only one method fired
  - `suggested_at` is a valid ISO-8601 UTC timestamp
  - `suggested_by` equals `f"smart_connect_v{CURRENT_SMART_CONNECT_VERSION}"`

- `test_connection_events.py`
  - promote call writes one row with `event_type='promote'`, correct
    `methods_json`, `confidence`, `tier`, `smart_connect_version`
  - dismiss call writes one row with `event_type='dismiss'`
  - backfill writes `backfill_suggested` rows; duplicate
    `(note_path, target_path, version)` on same day is skipped
  - stats aggregation groups promoted/dismissed counts by method correctly

- `test_connection_stats.py`
  - `notes_total` matches actual note count in DB
  - `method_breakdown` counts come from frontmatter scan, not `alias_index`
  - `semantic_orphans_with_suggestions` + `_without_suggestions`
    == `semantic_orphans_total`
  - `acceptance_rate` = promoted / (promoted + dismissed)
  - `acceptance_rate` is `null` when no events recorded

Frontend (`frontend/tests/components/`):

- `SuggestionsPanel.test.ts` (extend existing):
  - "Keep all" hidden when < 2 strong suggestions
  - "Keep all" hidden when > 5 strong suggestions
  - N = 2: promotes immediately (no confirmation)
  - N = 4: shows inline confirmation; Cancel stops all promotes
  - calls `promoteSuggestion()` sequentially for each strong item
  - emits `changed` once after all promotions
  - `score_breakdown` tooltip renders on hover (content matches breakdown data)
  - tooltip absent when `score_breakdown` not present

---

## Definition of Done

1. `SuggestedLink` carries `score_breakdown`, `suggested_at`, `suggested_by`
   (backwards-compatible).
2. `score_breakdown` written iff ≥ 2 signals fired; sums to `confidence`.
3. `connection_events` table created; promote and dismiss routes write to it.
4. `GET /api/connections/stats` returns full JSON above with correct
   computation sources.
5. "Keep all (N)" button in `SuggestionsPanel` (conditions and confirmation
   as specified).
6. "Why?" tooltip in `SuggestionsPanel` when `score_breakdown` present.
7. All tests above pass.
8. `docs/.registry.json` updated for all 26a/26b/26c/26d specs.
