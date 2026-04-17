# Step 22d — Soft Graph Edges with Confidence

> **Goal**: Produce derived, confidence-weighted edges that connect
> semantically related items: `same_topic_as`, `same_business_area_as`,
> `likely_dependency_on`, `implementation_of_same_problem`,
> `same_risk_cluster_as`. Edges are bounded, pruned and rebuildable.

**Status**: ⬜ Not started
**Depends on**: 22b (hard edges, node types), 22c (enrichment payloads),
step-19b (embeddings), step-20b (node embeddings), step-20c (chunk edges)
**Effort**: ~2 days

---

## Why soft edges must be separate from hard edges

Hard edges from Jira are authoritative. Derived edges are guesses. Mixing
them into the same weight space pollutes retrieval. The graph model
already has `weight` and (after 22b) `source`. This step adds one more
invariant: every derived edge must also carry `confidence` and
`generated_at`, and must be regenerable from inputs alone.

---

## Edge catalogue (derived only)

| Edge type                         | Signal                                                                 | Max out-degree per node | Confidence floor |
|-----------------------------------|------------------------------------------------------------------------|-------------------------|------------------|
| `same_topic_as`                  | cosine(node_embedding) ≥ 0.72 OR ≥ 2 chunk matches ≥ 0.78 each          | 8                       | 0.60             |
| `same_business_area_as`          | enrichment `business_area` match AND topic signal ≥ 0.55                | 10                      | 0.55             |
| `same_risk_cluster_as`           | same `(business_area, risk_level)` AND topic ≥ 0.60                     | 8                       | 0.60             |
| `likely_dependency_on`           | enrichment candidate key + forward-reference in text + no hard `blocks` | 5                       | 0.65             |
| `implementation_of_same_problem` | ≥ 3 chunk matches ≥ 0.80 AND same business_area                         | 6                       | 0.70             |

Edges are **asymmetric unless explicitly symmetric** (`same_*` are
symmetric and emitted in both directions; `likely_dependency_on` is
directed).

### Confidence formula (example)

```
confidence(same_topic_as, a, b) =
    0.55 * cos(node_a, node_b)
  + 0.35 * top_k_mean(chunk_cosine(a.*, b.*), k=3)
  + 0.10 * enrichment_keyword_jaccard(a, b)
```

All contributing signals are normalised to `[0,1]`. The formula and its
weights live in `services/graph_service/soft_edges.py` as pure
functions with unit tests.

---

## Rebuild pipeline

```
rebuild_soft_edges(workspace) →
    1. remove_edges_where_source("derived")
    2. candidate_pairs = ANN search per node (top-K by embedding)
    3. for each pair:
        a. compute signals
        b. compute confidence
        c. if confidence ≥ threshold: emit edge with source="derived",
           weight=confidence, evidence=top-k chunk pairs
    4. prune: enforce max out-degree per node per edge type
    5. persist graph + bump graph version
```

ANN: we re-use the exact cosine over stored node embeddings (workspace
sizes are small — O(N²) is fine for N ≤ 20 k). Above that, add HNSW via
`hnswlib` in a later step; not in scope here.

---

## Evidence

Every derived edge stores evidence suitable for the existing
`graph-evidence-ui` (step-20g):

```
Edge.evidence = (
    (source_chunk_idx, target_chunk_idx, similarity),
    ...
)
```

`same_business_area_as` edges additionally store the area name so the UI
can show *"Both tagged billing by enrichment v1"*.

---

## Pruning rules

Pruning runs at the end of every rebuild:

1. Per node, per edge type, keep top-K by confidence.
2. Drop edges below floor.
3. Drop edges between nodes that already have a stronger hard edge of a
   semantically superset relation (e.g. if `blocks` exists, drop
   `likely_dependency_on` for the same pair).
4. Drop self-loops.
5. If total derived edges > `5 × |nodes|`, raise all floors by +0.05 and
   re-prune. Prevents runaway growth on dense corpora.

---

## API + UI

- `POST /api/graph/rebuild-soft` → 202 with progress SSE.
- `GET /api/graph/edges?source=derived&type=same_topic_as` for inspection.
- Existing graph UI gets a "soft edges" toggle and a confidence slider
  (already scaffolded in step-20g — extend filter panel only).

---

## Tests

- `test_confidence_monotonic`: raising any input signal only raises
  confidence.
- `test_hard_edge_suppresses_soft`: if `blocks(a,b)` exists,
  rebuild emits no `likely_dependency_on(a,b)`.
- `test_topk_respected`: node with 50 similar neighbours keeps exactly
  `max_out_degree` edges, the top ones by confidence.
- `test_rebuild_deterministic`: same inputs → identical edge set
  (sort-stable, explicit tie-breaker on node id).
- `test_source_separation`: `remove_edges_where_source("derived")` does
  not touch `source="jira"` edges.

---

## Definition of done

- Running a rebuild after an import produces a bounded, stable set of
  derived edges with evidence.
- Graph UI shows derived edges with a distinct style and tooltip citing
  the evidence.
- `docs/features/soft-edges.md` authored.
