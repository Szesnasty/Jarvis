# Step 25 — Smart Connect (Cheap Per-Note Ingest-Time Linking)

> **Goal**: Add a thin orchestration layer that runs at ingest time and uses
> the building blocks Jarvis already has (FTS/BM25, note embeddings, chunk
> embeddings, entity extraction, frontmatter, graph) to **propose connections
> for the new note** — without AI, without a global rebuild, and without
> polluting the authoritative graph. The result is a `suggested_related`
> block in frontmatter, broader entity coverage in the graph, and an
> incremental graph update path that scales as memory grows.

**Status**: ⬜ Not started
**Depends on**: 04 (memory + FTS), 08 (graph), 14a (entity extraction),
14b (graph refinement), 19a (BM25), 19b (embeddings), 20c (chunk edges),
20d (entity canonicalization)
**Related** (intentionally distinct, see "Boundaries" below): 22d (soft edges, global)
**Effort**: ~3 days backend + 0.5 day frontend

---

## Why this exists

Today the ingest path in [backend/services/ingest.py](backend/services/ingest.py#L66-L139) is:

```
fast_ingest()
  → write Markdown
  → memory_service.index_note_file()        # FTS + note/chunk embeddings
  → graph_service.rebuild_graph()           # FULL rebuild, every upload
```

Three problems with this:

1. **Full `rebuild_graph()` after every upload** is fine at 50 notes, painful
   at 5 000, and a tax on every single drag-and-drop. The incremental
   alternative [`graph_service.ingest_note()`](backend/services/graph_service/queries.py#L152) exists but skips
   similarity, temporal, IDF re-weighting, bidirectional link resolution and
   tag pruning — so swapping it in 1:1 silently degrades the graph.
2. **The cheap signals already produced at ingest are never used to suggest
   links.** The new note has fresh BM25 rows, a fresh note embedding and
   fresh chunk embeddings — yet nothing asks "what is this note adjacent
   to?" until the next global rebuild (which only computes generic
   `similar_to` over the whole corpus).
3. **Entity extraction returns `person | organization | project | place |
   date`**, but [`_enrich_with_entities()`](backend/services/graph_service/builder.py#L78) only writes `person` nodes
   to the graph. Free signal is being thrown away.

Step 22d (soft edges) addresses (2) and (3) at the **global** level via a
batch rebuild. Step 25 addresses them at the **per-note** level at ingest
time, which is what the user actually feels.

---

## Boundaries vs. Step 22d (soft edges)

| Concern                         | Step 22d (soft edges)                  | Step 25 (smart connect)                  |
|---------------------------------|----------------------------------------|------------------------------------------|
| Trigger                         | Manual / batch / scheduled rebuild     | Per-note, on every ingest                |
| Scope                           | All nodes, all pairs                   | One new note vs. the rest                |
| Output                          | Derived edges in graph (`source=derived`) | `suggested_related` in frontmatter + non-`related` graph edges |
| Touches `related:` frontmatter? | No                                     | Never automatically — user-confirmed only |
| Cost model                      | O(N²) bounded by ANN                   | O(top-K) candidates per note             |
| AI use                          | None                                   | Optional re-rank, post candidate generation |

Step 25 must **not** duplicate step 22d's edge catalogue. It writes
suggestions, plus a small set of cheap **per-note** edges (alias, source,
batch, broader entity types) that don't need a global pass. Anything that
genuinely requires global knowledge (e.g. `same_risk_cluster_as`) stays in
22d.

---

## Architectural decisions

### 1. New module: `services/connection_service.py`

Single entry point used by every ingest path:

```python
async def connect_note(
    note_path: str,
    workspace_path: Optional[Path] = None,
    mode: Literal["fast", "aggressive"] = "fast",
) -> ConnectionResult:
    ...
```

`ConnectionResult` (Pydantic) returns:

```python
class SuggestedLink(BaseModel):
    path: str
    confidence: float
    methods: list[str]          # ["bm25", "note_embedding", "chunk_embedding", ...]
    evidence: str | None        # short human-readable reason

class EntityCounts(BaseModel):
    people: int
    organizations: int
    projects: int
    places: int

class ConnectionResult(BaseModel):
    note_path: str
    suggested: list[SuggestedLink]      # written to frontmatter
    strong_count: int                   # confidence ≥ 0.80
    aliases_matched: list[str]          # exact title/alias hits
    entities: EntityCounts
    graph_edges_added: int
```

### 2. `connect_note()` is the single ingest-time orchestrator

Pipeline:

```
1. read note (frontmatter + body)
2. build connection_query = title + headings + tags + first 800 chars
3. parallel candidate generation:
   - bm25_hits      = memory_service.search_notes(connection_query, limit=15)
   - note_emb_hits  = embedding_service.search_similar_notes(query=note_emb, limit=10)
   - chunk_hits     = embedding_service.search_similar_chunks(connection_query, limit=10)
   - alias_hits     = alias_index.scan(title + headings + first 800 chars)
   - entity_overlap = entity_index.notes_sharing(extracted_entities, limit=20)
4. merge candidates → score → prune → cap (see §6)
5. write suggested_related block to frontmatter
6. add per-note graph edges (see §3)
7. graph_service.ingest_note(note_path)        # incremental, edges from §3 already in
8. return ConnectionResult
```

No global rebuild. No AI. The whole pass must finish in under ~300 ms for a
typical note on a workspace of a few thousand notes (target — verify in
`tests/test_connection_service_perf.py`).

### 3. New per-note edge types (extend `_EDGE_BASE_WEIGHT`)

Add to [_EDGE_BASE_WEIGHT in models.py](backend/services/graph_service/models.py#L131):

| Type                | Base weight | When emitted                                                 |
|---------------------|-------------|--------------------------------------------------------------|
| `suggested_related` | 0.35        | Each candidate above floor 0.45                              |
| `alias_match`       | 0.75        | Exact title/alias hit in body                                |
| `derived_from`     | 0.45        | Note → `source:<hash>` node (see §5)                         |
| `same_batch`       | 0.55        | Note → `batch:<id>` node (set by structured/Jira ingest)     |
| `mentions_org`     | 0.55        | Note → `org:<canonical>`                                     |
| `mentions_project` | 0.70        | Note → `project:<canonical>`                                 |
| `mentions_place`   | 0.35        | Note → `place:<canonical>`                                   |

`related` (0.9) is reserved for **user-confirmed** links. Suggestions never
write `related` automatically. Dates are deliberately **not** added as
nodes (they create dense, low-signal stars); we will use them for temporal
clustering in a separate step.

### 4. Broader entity expansion in the graph

Refactor [`_enrich_with_entities()` in builder.py](backend/services/graph_service/builder.py#L78) and the entity
block in [`ingest_note()` in queries.py](backend/services/graph_service/queries.py#L152) to use a single shared
table:

```python
_ENTITY_EDGE = {
    "person":       ("person",  "mentions",          0.8),
    "organization": ("org",     "mentions_org",      0.55),
    "project":      ("project", "mentions_project",  0.70),
    "place":        ("place",   "mentions_place",    0.35),
}
```

Apply canonicalization (already wired for `person` via
[`entity_canonicalization`](backend/services/entity_canonicalization.py)) to `org` and `project` as well.
`place` skips canonicalization for v0 — too noisy.

### 5. Source and batch as first-class nodes

`fast_ingest()` already writes `source` to frontmatter via
[`_make_frontmatter()` in ingest.py](backend/services/ingest.py#L41-L47). `connect_note()` must:

- Compute `source_id = "source:" + sha1(source)[:12]`.
- Add a `source` node with a human-readable label
  (`url_ingest` URL, `pdf:filename`, `jira:export-…`).
- Emit `note → source_id` with type `derived_from`.

For structured imports (CSV/XML/Jira), [`structured_ingest`](backend/services/structured_ingest.py)
must also set `batch_id` in frontmatter and emit
`note → batch:<id>` with `same_batch`. Jira's overview/group/issue
hierarchy gets explicit edges as already proposed in step 22e
(no duplication — keep them there).

### 6. Scoring and pruning

Pure function in `services/connection_service.py`, unit-tested:

```python
score = (
    0.30 * bm25_norm
  + 0.30 * note_embedding_norm
  + 0.20 * chunk_embedding_norm
  + 0.10 * entity_overlap
  + 0.07 * alias_match
  + 0.03 * same_source
)
```

All inputs normalised to `[0,1]` per call (max-normalise within candidate
set). Tiers:

| Score        | Action                                                     |
|--------------|------------------------------------------------------------|
| ≥ 0.80       | `strong` — UI flags for one-click promote to `related`     |
| 0.60–0.79    | `normal` suggestion                                        |
| 0.45–0.59    | `weak` — only kept if note is a *semantic orphan* (§8)     |
| < 0.45       | drop                                                       |

Caps per note:

- max **5** `suggested_related` total
- max **2** from the same folder
- max **1** near-duplicate (cosine ≥ 0.92) unless score ≥ 0.85

### 7. Alias matcher

New `alias_index` table (SQLite) populated on every ingest:

```sql
CREATE TABLE IF NOT EXISTS alias_index (
    phrase_norm TEXT NOT NULL,    -- lowercased, accent-stripped
    note_path   TEXT NOT NULL,
    kind        TEXT NOT NULL,    -- 'title' | 'alias' | 'heading'
    PRIMARY KEY (phrase_norm, note_path, kind)
);
CREATE INDEX IF NOT EXISTS idx_alias_phrase ON alias_index(phrase_norm);
```

Frontmatter gains:

```yaml
title: Hybrid Retrieval Pipeline
aliases:
  - RAG pipeline
  - retrieval pipeline
  - wyszukiwanie hybrydowe
```

Lookup: tokenise note body into n-grams (n=1..4), normalise, exact match
against `alias_index`. Hits below 4 chars are dropped. Aliases owned by the
note itself are excluded.

### 8. Semantic orphan repair

Replace `find_orphans()` semantics with a second function — keep the
original for backwards compatibility:

```python
def find_semantic_orphans(
    workspace_path: Optional[Path] = None,
    ignore_edge_types: set[str] = {"tagged", "part_of", "temporal", "derived_from"},
    ignore_tags: set[str] = {"imported", "data", "xml", "csv"},
) -> list[dict]: ...
```

A note is a semantic orphan if it has **zero** edges of types not in
`ignore_edge_types`, and any tag edges only point at tags in
`ignore_tags`. When `connect_note()` produces zero suggestions ≥ 0.60 for a
new note, it re-runs in `mode="aggressive"` (lower BM25 thresholds, larger
candidate pools, accept `weak` tier).

### 9. Slug fix for non-ASCII titles

[`_slugify()` in ingest.py](backend/services/ingest.py#L25) strips non-ASCII, so Polish titles
collapse. Replace with NFKD-normalising version (proposal §11). This is a
prerequisite for alias matching working on Polish content.

### 10. Replace global rebuild in the ingest path

In [`fast_ingest()`](backend/services/ingest.py#L128-L132), replace:

```python
from services.graph_service import rebuild_graph
rebuild_graph(workspace_path=workspace_path)
```

with:

```python
from services.connection_service import connect_note
result = await connect_note(rel_path, workspace_path=workspace_path)
return {**base_result, "connections": result.dict()}
```

`connect_note()` calls `graph_service.ingest_note()` internally so a single
note is reflected in the graph immediately.

`rebuild_graph()` remains the canonical pass and is still called for:

- Batch imports (after the whole batch — keep [structured_ingest.py](backend/services/structured_ingest.py)
  behaviour as-is).
- "Reindex all" / "Repair graph" buttons (step 23e).
- Algorithm version bumps.

### 11. AI sharpen as opt-in re-rank, not default

Keep [`smart_enrich()`](backend/services/ingest.py#L143) for summary + tags. Add a separate, opt-in
`smart_connect_rerank(note_path, candidates)` that takes the top-10
candidates from §2, sends only their titles + summaries + the new note's
summary to Claude, and asks for top-3 with reasons. Gated by indexing
control (step 23) — never runs unless the user enabled LLM enrichment.
Output replaces the `suggested` block; `confidence` is overwritten with a
blended value (`0.7 * heuristic + 0.3 * model_rank_norm`).

---

## API surface

All new endpoints under `/api/connections/`:

| Method | Path                                  | Purpose                                              |
|--------|---------------------------------------|------------------------------------------------------|
| POST   | `/api/connections/run/{path}`         | Re-run `connect_note` for an existing note           |
| GET    | `/api/connections/suggestions/{path}` | Read current `suggested_related` block               |
| POST   | `/api/connections/promote`            | Move a suggestion into `related:` (user confirms)    |
| POST   | `/api/connections/dismiss`            | Drop a suggestion and remember the dismissal         |
| GET    | `/api/connections/orphans`            | List semantic orphans                                |

Dismissals are stored in `app/jarvis.db`:

```sql
CREATE TABLE IF NOT EXISTS dismissed_suggestions (
    note_path   TEXT NOT NULL,
    target_path TEXT NOT NULL,
    dismissed_at TEXT NOT NULL,
    PRIMARY KEY (note_path, target_path)
);
```

`connect_note()` filters dismissed pairs out of every future run.

---

## Frontend (minimal in this step)

- Upload response shows: `Imported. Jarvis found N possible connections.`
  with **Review** / **Accept all strong** / **Ignore** buttons.
  Acceptance maps to `POST /api/connections/promote`.
- Memory page: a small "Suggested" badge on notes with pending suggestions.
- Full review UI lives in a follow-up frontend spec (25b) — keep this step's
  frontend change small.

---

## Tests

Backend (in [backend/tests/](backend/tests/)):

- `test_connection_service_scoring.py` — pure scoring function: monotonic in each
  signal; caps respected; near-duplicate filter.
- `test_connection_service_pipeline.py` — end-to-end with a fixture
  workspace: alias hit, BM25 hit, chunk hit, entity overlap.
- `test_connection_service_orphan.py` — semantic orphan triggers
  aggressive mode.
- `test_connection_service_perf.py` — ≤ 300 ms on a 2 000-note fixture
  (skipped on CI when fixture missing).
- `test_alias_index.py` — index population, n-gram lookup, NFKD
  normalisation, Polish characters.
- `test_graph_entity_expansion.py` — `org`, `project`, `place` nodes and
  edges produced by both `rebuild_graph()` and `ingest_note()`.
- `test_ingest_no_full_rebuild.py` — `fast_ingest()` does **not** call
  `rebuild_graph()`; calls `connect_note()` exactly once.
- `test_dismissed_suggestions.py` — dismissed pairs never reappear.

---

## Migration

- Add `aliases: []` and `suggested_related: []` to the frontmatter contract
  in [utils/markdown.py](backend/utils/markdown.py); preserve unknown keys (already done).
- One-shot migration script `scripts/backfill_connections.py`:
  1. Iterate every note.
  2. Run `connect_note()` once.
  3. Print a summary (notes touched, suggestions added, orphans found).
  Run it from the "Reindex all" UI action (step 23e) and from CLI.
- No SQLite migration beyond the two new tables (`alias_index`,
  `dismissed_suggestions`) — both created on first use.

---

## Definition of Done

1. `connect_note()` exists and is the single ingest-time orchestrator.
2. `fast_ingest()` no longer calls `rebuild_graph()`; structured ingest is
   unchanged.
3. Frontmatter `suggested_related` is populated; `related` is never
   auto-written.
4. Graph emits `org`, `project`, `place`, `source`, `batch`,
   `alias_match`, `suggested_related` edges with the weights in §3.
5. Semantic orphan detection runs and triggers aggressive mode when
   warranted.
6. Polish slugs survive NFKD normalisation.
7. All backend tests above pass; perf test passes on the fixture.
8. Upload UI shows the connection preview with Review / Accept / Ignore.
9. Documentation registry updated; this spec linked from
   [docs/steps/step-00-index.md](docs/steps/step-00-index.md).

---

## Out of scope (deferred)

- Full review UI (separate spec 25b).
- Auto-promotion of suggestions (always user-confirmed).
- HNSW / ANN — exact cosine is fast enough at MVP scale.
- Cross-workspace suggestions.
- Date entities as graph nodes (use temporal edges instead).
- Anything covered by step 22d (global derived edges) — do not duplicate.
