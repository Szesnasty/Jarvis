---
title: Soft Edges (Derived Graph Edges)
last_updated: 2026-04-17
status: current
---

# Soft Edges — Derived Graph Edges with Confidence

## Summary

Soft edges are confidence-weighted graph edges derived from embeddings, enrichment payloads and text signals. Unlike hard edges (from Jira or frontmatter), soft edges are **guesses** that carry a confidence score and are fully rebuildable from inputs. They use `origin="derived"` so they can be filtered, toggled and regenerated independently.

## Edge Catalogue

| Edge Type | Signal | Max Out-Degree | Confidence Floor |
|-----------|--------|----------------|------------------|
| `same_topic_as` | node cosine + chunk sims + keyword Jaccard | 8 | 0.60 |
| `same_business_area_as` | enrichment area match + topic signal | 10 | 0.55 |
| `same_risk_cluster_as` | same (area, risk_level) + topic signal | 8 | 0.60 |
| `likely_dependency_on` | text forward-reference + topic (suppressed by hard `blocks`) | 5 | 0.65 |
| `implementation_of_same_problem` | ≥3 chunk matches ≥0.80 + same area | 6 | 0.70 |

Symmetric edges (`same_*`) are emitted in both directions. `likely_dependency_on` is directed.

## Confidence Formulas

### same_topic_as

```
confidence = 0.55 * cos(node_a, node_b)
           + 0.35 * top_k_mean(chunk_cosines, k=3)
           + 0.10 * keyword_jaccard(a, b)
```

### same_business_area_as

Returns 0 if areas don't match. Otherwise: `0.50 + 0.50 * topic_signal`.

### same_risk_cluster_as

Returns 0 if (area, risk) pair doesn't match. Otherwise: `0.50 + 0.50 * topic_signal`.

### likely_dependency_on

Returns 0 if a hard `blocks`/`depends_on` edge exists or no forward text reference found. Otherwise: `0.40 + 0.60 * topic_signal`.

### implementation_of_same_problem

Requires ≥3 chunk pairs with cosine ≥0.80 AND same business area. `0.40 + 0.35 * best_chunk_sim + 0.25 * count_factor`.

## How It Works

### Rebuild Pipeline

1. **Remove** all edges with `origin="derived"`
2. **Load signals**: node embeddings, chunk embeddings, enrichment payloads, hard edge index
3. **For each pair** of enrichable nodes (issue/note):
   - Compute shared signals (node cosine, chunk sims, keyword Jaccard)
   - Evaluate confidence for each edge type
   - Emit edge if confidence ≥ floor
4. **Prune**: enforce max out-degree per node per type, drop self-loops, suppress soft edges where hard edge superset exists
5. **Density cap**: if total derived edges > 5 × |nodes|, raise all floors by +0.05 and re-prune

### Integration

Soft edges are computed as **Pass 10** of `rebuild_graph()` in the builder, after Jira projection (Pass 8) and node embeddings (Pass 9). They can also be rebuilt independently via the API.

## Key Files

| File | Purpose |
|------|---------|
| `backend/services/graph_service/soft_edges.py` | Core module: signals, confidence formulas, rebuild, pruning |
| `backend/services/graph_service/builder.py` | Pass 10 integration |
| `backend/routers/graph.py` | API: `POST /rebuild-soft`, `GET /edges` |
| `backend/tests/test_soft_edges.py` | 10 tests (6 unit, 4 integration) |

## API

### `POST /api/graph/rebuild-soft`

Rebuild all derived edges. Returns `{status, edges_added}`.

### `GET /api/graph/edges?origin=derived&type=same_topic_as`

List edges with optional `origin` and `type` filters. Returns array of edge objects with evidence.

## Pruning Rules

1. Per node, per edge type: keep top-K by confidence
2. Drop below confidence floor
3. Drop `likely_dependency_on` if hard `blocks`/`depends_on` exists for same pair
4. Drop self-loops
5. Density cap: total derived edges ≤ 5 × |nodes|; raise floors by +0.05 increments if exceeded
