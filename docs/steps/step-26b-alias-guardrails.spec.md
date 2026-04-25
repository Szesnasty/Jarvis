# Step 26b — Alias Guardrails & Retrieval Edge Classification

> **Goal**: Prevent the alias matcher from generating noise-driven suggestions
> by enforcing length/stopword/frequency rules and a `weak_aliases` signal
> tier. Also correctly classify provenance edges so they don't mask semantic
> orphans.

**Status**: ✅ Implemented
**Depends on**: Step 26a (versioning constants used in tests)
**Effort**: ~1 day backend

---

## Why this step exists

After backfill runs, the alias matcher will be exercised at scale for the
first time. Without guardrails it will break trust fast: aliases like `AI`,
`API`, `memory`, `graph`, or `model` appear in hundreds of notes and will
produce near-universal matches. A single over-broad alias destroys precision
for every note that carries it.

The retrieval guard problem is orthogonal but belongs here because it also
protects the orphan classifier from false negatives: notes with only
`derived_from` or `same_batch` edges should still be treated as semantic
orphans.

---

## Changes

### 1. Alias guardrails in `alias_index.upsert_note_aliases()`

#### 1a. Minimum length + short-acronym allowlist

Reject phrases below 4 characters, **except** those in a module-level
allowlist of common discriminative acronyms:

```python
_ALIAS_SHORT_ALLOWLIST = {
    "aws", "jwt", "sql", "css", "gpu", "cpu",
    "ui", "ux", "s3", "k8s", "ci", "cd",
}
```

This is a deliberate design decision: the 4-char floor blocks noise (random
tokens, short stopwords), while the allowlist preserves acronyms that are
genuinely discriminative. The allowlist is small and explicit — extending it
requires a conscious edit, not just a yaml entry.

#### 1b. Stopword list

Module-level set of broad terms that are too generic to discriminate between
notes:

```python
_ALIAS_STOPWORDS = {
    "ai", "api", "ml", "nlp", "llm", "rag", "etl",
    "memory", "graph", "model", "data", "note", "file",
    "notes", "docs", "doc", "page", "item", "record",
    "list", "plan", "task", "work", "project",
}
```

Phrases that consist **entirely** of `_ALIAS_STOPWORDS` tokens are silently
rejected. Mixed phrases are allowed: `"AI assistant"` passes (one content
word), `"AI"` alone does not.

#### 1c. Frequency cap — computed BEFORE insert

```python
threshold = max(10, ceil(total_notes * 0.05))
existing_count = count_distinct_notes_for_phrase(phrase_norm)

if existing_count >= threshold and note_path not already indexed_for_phrase:
    # phrase is too common — do not insert
    return
# else: proceed with upsert
```

`total_notes` is cached once per calling context (e.g. per backfill call or
per ingest batch) to avoid N+1 queries. The cap runs before the DB write, so
a blocked phrase never appears in the index for the new note.

Required SQL indexes (add migration in `database.py`):

```sql
CREATE INDEX IF NOT EXISTS idx_alias_index_phrase_norm
  ON alias_index(phrase_norm);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alias_index_phrase_note_kind
  ON alias_index(phrase_norm, note_path, kind);
```

#### 1d. `weak_aliases` frontmatter key

Honour a new optional frontmatter field:

```yaml
aliases:
  - "hybrid retrieval pipeline"   # strong — can independently produce a suggestion
weak_aliases:
  - "retrieval"                   # weak — only contributes if another signal also fires
```

`weak_aliases` entries are indexed with `kind = 'weak_alias'`.

**Strict rule**:

> A `weak_alias` hit alone MUST NOT emit a suggestion. It only contributes
> to candidates where at least one non-alias signal (`bm25`, `note_emb`, or
> `chunk_emb`) has already fired.

When a candidate qualifies for a suggestion via another signal, a
`weak_alias` hit adds **0.35** to the per-candidate alias score instead
of the normal **1.0**. A `weak_alias` cannot independently push a
candidate to `strong` tier.

### 2. Retrieval guard — provenance and unconfirmed edges

`derived_from`, `same_batch`, and `suggested_related` edges are NOT
semantic relations:

- `derived_from` / `same_batch` = provenance (origin of the content)
- `suggested_related` = unconfirmed Smart Connect candidate

These edge types must NOT rescue a note from semantic orphan status.

Update `find_semantic_orphans()` default `ignore_edge_types` in
`graph_service/queries.py`:

```python
DEFAULT_IGNORE_EDGE_TYPES = frozenset({
    "tagged", "part_of", "temporal",
    "derived_from", "same_batch",      # provenance — not semantic
    "suggested_related",               # unconfirmed — not semantic
})
```

Retrieval scorer: `suggested_related` edges contribute at most
`min(weight, 0.35)` to a node's graph score. They provide a soft
discovery signal but cannot dominate retrieval ranking before user review.

The value `0.35` is exposed as a module-level constant
`SUGGESTED_RELATED_MAX_WEIGHT` in `graph_service/queries.py` so that
Step 26d (Controlled Graph Expansion) can import the same value and the
two paths cannot drift.

---

## API surface

No new endpoints. Changes are internal to `alias_index.py` and
`graph_service/queries.py`.

---

## Tests

Backend (`backend/tests/`):

- `test_alias_guardrails.py`
  - phrase `"ab"` (2 chars) → rejected
  - phrase `"jwt"` (in allowlist) → accepted despite being 3 chars
  - phrase `"aws"` (in allowlist) → accepted
  - phrase `"AI"` (stopword only) → rejected
  - phrase `"memory"` (stopword only) → rejected
  - phrase `"AI assistant"` (stopword + content word) → accepted
  - phrase `"data model"` (two stopwords) → rejected
  - frequency cap: setup 10+ notes with same phrase; 11th note → phrase blocked
  - cap check confirmed BEFORE insert (DB state inspected after blocked attempt)
  - `"retrieval"` in `weak_aliases:` → indexed with `kind='weak_alias'`
  - `weak_alias` alone → no `SuggestedLink` emitted
  - `weak_alias + bm25_hit` → `SuggestedLink` emitted
  - `weak_alias` contribution to score = 0.35, normal alias = 1.0
  - `weak_alias` alone cannot produce `tier='strong'`

- `test_pl_slug_alias.py` (Polish regression)
  - `"Łódź"` → normalised to `"lodz"`
  - `"Zażółć gęślą jaźń"` → `"zazolc-gesla-jazn"`
  - `"Świnoujście"` → `"swinoujscie"`
  - `"Michał"` → `"michal"`
  - `"żółć"` → `"zolc"`
  - alias scan: `"wyszukiwanie hybrydowe"` matches stored alias
    `"Wyszukiwanie hybrydowe"`
  - alias scan: body text `"Łódź"` matches normalised alias `"lodz"`

- Extended `test_connection_service_orphan.py`
  - note with only `derived_from` edge → still a semantic orphan
  - note with only `same_batch` edge → still a semantic orphan
  - note with only `suggested_related` edge → still a semantic orphan
  - note with a user-confirmed `related` edge → NOT a semantic orphan
  - retrieval scorer: `suggested_related` edge weight capped at 0.35 in
    graph score computation

---

## Definition of Done

1. `upsert_note_aliases()` enforces min-length + allowlist, stopword set,
   pre-insert frequency cap.
2. `weak_aliases:` frontmatter field parsed and indexed with `kind='weak_alias'`.
3. `weak_alias` alone never emits a suggestion (enforced in scorer, tested).
4. Required SQL indexes present in migration.
5. `find_semantic_orphans()` default `ignore_edge_types` includes `derived_from`,
   `same_batch`, `suggested_related`.
6. Retrieval scorer caps `suggested_related` contribution at 0.35.
7. All tests above pass including Polish slug regression suite.
