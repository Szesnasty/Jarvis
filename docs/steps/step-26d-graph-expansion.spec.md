# Step 26d — Controlled Graph Expansion in Chat Retrieval

> **Goal**: Make Smart Connect actually *pay off* in conversations. Chat
> retrieval pulls user-confirmed `related` edges, strong `suggested_related`
> candidates, and project (`part_of`) edges as bounded extra context — with
> edge-type-aware weights, fan-out caps, and a token budget.

**Status**: ⬜ Not started
**Depends on**: Step 26b (edge classification, retrieval guard for
`suggested_related`, `weak_alias` semantics)
**Effort**: ~1 day backend + small frontend touch

---

## Why this step exists

Steps 25, 26a, 26b, 26c connect notes, clean the signals, and surface the
result in the UI. But the chat pipeline still treats the graph the same way
it did before Smart Connect existed: a single `_compute_graph_score()` that
walks edges uniformly without distinguishing user-confirmed `related` from
provenance (`derived_from`, `same_batch`) or unconfirmed
`suggested_related`.

This is the missing payoff. Until chat retrieval *expands* through
high-trust edges, all the connection work in 25/26a/26b/26c is invisible
to the actual answers. Per the project's own assessment, this is the
single change with **the largest impact on answer quality**.

The retrieval guard from 26b is the defensive half (don't let unconfirmed
links dominate). This step is the offensive half (do let confirmed and
strong-suggested links contribute).

---

## Changes

### 1. Edge-type expansion weights

Add a single source of truth in `services/retrieval/pipeline.py`:

```python
# Per-edge weights for chat retrieval expansion.
# Keys are edge `type` values; missing types default to 0.0 (ignored).
EXPANSION_EDGE_WEIGHTS: dict[str, float] = {
    "related":            1.00,  # user-confirmed
    "part_of":            0.60,  # project / area membership
    "mentions":           0.50,  # explicit body mention
    "similar_to":         0.45,  # semantic cluster
    "suggested_related":  0.35,  # unconfirmed — capped (matches 26b guard)
    # Explicitly excluded (weight 0.0):
    # "derived_from", "same_batch" → provenance, not semantic
    # "tagged", "temporal"          → too broad to drive expansion
}
```

`suggested_related` weight (0.35) MUST equal the cap defined in 26b. The
two values share a single named constant `SUGGESTED_RELATED_MAX_WEIGHT`
imported from `graph_service/queries.py` to prevent drift.

**Tier-aware downgrade**: when an edge has `type='suggested_related'` and
the corresponding `SuggestedLink` has `tier != 'strong'`, weight is
multiplied by 0.5 (final ≤ 0.175). `weak_alias`-only suggestions are
excluded from expansion entirely (weight = 0.0).

### 2. Bounded expansion in `_compute_graph_score`

Refactor `_compute_graph_score()` so edge contributions are weighted by
type, not flat:

```python
for edge in graph.edges:
    other = ...
    type_weight = EXPANSION_EDGE_WEIGHTS.get(edge.type, 0.0)
    if type_weight == 0.0:
        continue
    if other in candidate_ids:
        edge_score += edge.weight * type_weight
        neighbor_ids.add(other)
```

The convergence bonus (3+ neighbours → +0.3) and cluster bonus remain, but
operate on the filtered neighbour set (provenance and excluded types do
not count toward convergence).

### 3. Anchor expansion in retrieval pipeline

Today the pipeline assembles `anchor_nodes` from explicit query entities
only. Extend `pipeline.py` to expand anchors by one hop along high-trust
edge types **before** scoring candidates:

```python
def _expand_anchors(
    graph: graph_service.Graph,
    anchors: list[str],
    *,
    max_added: int = 8,
) -> list[str]:
    """Add one-hop neighbours via high-trust edges to the anchor set.

    - Includes neighbours via 'related' (full weight).
    - Includes neighbours via 'part_of' (project membership) so notes in
      the same project are reachable from any of them.
    - Includes 'suggested_related' ONLY when tier == 'strong'.
    - Sorted by edge weight × type_weight, capped at max_added.
    - Original anchors always retained.
    """
```

`max_added = 8` is per call; the cap prevents fan-out explosions on dense
hubs (e.g. a project note linked to 100 sub-notes). The expanded anchor
set feeds `_score_by_path()` exactly as before.

### 4. Token budget for expanded context

`context_builder.py` currently appends graph neighbours (depth=2) without
a separate budget. Split the assembly:

- **Core context**: top BM25 + embedding hits within their existing budget.
- **Graph expansion context**: notes pulled in *only* via the expansion
  weights from §1, capped at:
  - `max_expansion_notes = 6`
  - `max_expansion_tokens = 1500` (rough char/4 estimate is sufficient)

When the cap is hit, expansion notes are sorted by
`edge_weight × EXPANSION_EDGE_WEIGHTS[edge.type]` descending and trimmed.
Core context is never trimmed to make room for expansion.

Each expansion note included in the final prompt is tagged with its
provenance edge so the trace explains *why* it was added:

```
[expansion via related]   projects/retrieval.md
[expansion via part_of]   projects/jarvis/index.md
[expansion via suggested] notes/retrieval-pipeline.md  (tier=strong, conf=0.84)
```

This trace is logged via existing token-tracking, not shown to the user.

### 5. Settings toggle

Add to `frontend/app/pages/settings.vue` (Memory sub-panel):

```
Graph expansion in chat retrieval
  [x] Use confirmed `related` links              (default: on)
  [x] Use project (`part_of`) membership         (default: on)
  [ ] Use strong `suggested_related` candidates  (default: off — opt-in)
```

The third toggle is **off by default**. Strong unconfirmed suggestions
are valuable but should be opt-in until users have reviewed at least some
of them. Persisted to `app/config.json` under
`retrieval.graph_expansion`:

```json
{
  "retrieval": {
    "graph_expansion": {
      "use_related": true,
      "use_part_of": true,
      "use_suggested_strong": false
    }
  }
}
```

When `use_suggested_strong = false`, `suggested_related` weight is forced
to 0.0 in `EXPANSION_EDGE_WEIGHTS` for that request (regardless of tier).

---

## API surface

No new endpoints. Settings reuses the existing config write path (whatever
26a's Backfill UI uses to persist Settings flags).

Internal:

- `EXPANSION_EDGE_WEIGHTS` (constant)
- `SUGGESTED_RELATED_MAX_WEIGHT` (shared constant in
  `graph_service/queries.py`)
- `_expand_anchors()` (new helper)
- `context_builder.assemble_context()` gains separate core / expansion
  buckets with caps.

---

## Tests

Backend (`backend/tests/`):

- `test_retrieval_graph_expansion.py`
  - `related` edge contributes at full weight (1.00) to graph score
  - `derived_from` edge contributes 0.0 (excluded)
  - `same_batch` edge contributes 0.0 (excluded)
  - `suggested_related` strong-tier edge weight ≤ 0.35
  - `suggested_related` non-strong-tier edge weight ≤ 0.175
  - convergence bonus only counts neighbours via expansion-eligible edge
    types
  - `_expand_anchors()` adds at most `max_added` neighbours
  - `_expand_anchors()` includes `related` neighbours, excludes
    `derived_from` neighbours
  - `_expand_anchors()` excludes non-strong `suggested_related`

- `test_context_builder_expansion_budget.py`
  - core context never trimmed in favour of expansion
  - expansion notes capped at `max_expansion_notes`
  - expansion notes capped at `max_expansion_tokens` (synthetic long notes)
  - notes excluded by cap are the ones with lowest
    `edge_weight × type_weight`
  - trace lines list each expansion note with its edge type

- `test_retrieval_settings_toggle.py`
  - `use_suggested_strong=false` → no `suggested_related` edge contributes
    regardless of tier
  - `use_part_of=false` → `part_of` edges contribute 0.0
  - `use_related=false` → `related` edges contribute 0.0
  - default config (no overrides) matches §5 defaults

- Regression: existing `_compute_graph_score` tests still pass with new
  per-type weighting (provenance edges that previously contributed must
  now contribute 0.0 — update fixtures accordingly).

Frontend (`frontend/tests/components/`):

- Settings panel: three toggles render with correct defaults; flipping
  any toggle PUTs the new `retrieval.graph_expansion` shape.

---

## Definition of Done

1. `EXPANSION_EDGE_WEIGHTS` defined; `_compute_graph_score()` uses
   per-type weights.
2. `SUGGESTED_RELATED_MAX_WEIGHT` is a single shared constant used by
   both 26b's retrieval guard and this step's expansion weights.
3. `_expand_anchors()` adds one-hop high-trust neighbours, capped at 8.
4. `context_builder` separates core vs. expansion budgets; expansion
   capped at 6 notes / 1500 tokens.
5. Trace logs name the edge type for every expansion note.
6. Settings UI exposes the three toggles with defaults specified in §5;
   `use_suggested_strong` defaults to **off**.
7. All tests above pass; provenance-edge regression fixtures updated.
8. `docs/.registry.json` entry added for this spec.

---

## Out of scope

- Multi-hop expansion (>1) — keep depth at 1 for this step; the
  convergence bonus already rewards densely connected neighbourhoods.
- Personalized PageRank or any global graph algorithm — too expensive
  per request and not needed at MVP scale.
- Auto-tuning of `EXPANSION_EDGE_WEIGHTS` from `connection_events` — that
  is a future step once 26c has accumulated enough promote/dismiss data.
