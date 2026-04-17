# Cross-Source Linking

> Step 22e — connects Jira issues, notes, decisions, PDFs and URL ingests
> at the fragment (chunk) level.

## Summary

Cross-source linking extends the chunk-level graph edge mechanism from
step 20c so every source type participates.  It emits derived edges that
cross source type boundaries (note→issue, issue→decision, etc.) and
intra-file edges for long documents.

All edges carry `origin="cross_source"` or `origin="intra_file"` and
are fully rebuildable.

## How It Works

### Phase 1 — Direct mentions

Scans all note bodies for issue keys (wiki-link `[[ONB-142]]` or bare
`ONB-142`).  Emits `mentions_issue` (note→issue) and
`mentioned_in_note` (issue→note) edges with confidence 0.95.

### Phase 2 — Cross-type semantic edges

For each (issue, note) pair ranked by node embedding similarity
(ANN top-40):

| Edge type | Trigger |
|-----------|---------|
| `about_same_topic_as` | ≥ 2 chunk matches ≥ 0.78 AND ≥ 1 shared canonical entity |
| `implements_decision` | ≥ 2 chunk matches ≥ 0.78 AND enrichment `execution_type` = implementation + decision |
| `derived_from_research` | ≥ 2 chunk matches ≥ 0.75 AND enrichment `execution_type` = investigation |

Enrichment compatibility biases (`±0.05–0.10`) are documented in
`ENRICHMENT_COMPAT` table inside the module, and unit-tested.

### Phase 3 — Intra-file chunk connections

For subjects with > 8 chunks, connects distant chunks (`|i - j| ≥ 3`)
with cosine ≥ 0.80 via `same_document_thread` edges (max 3 per chunk,
forward direction only).

### Pruning

- Per-node max out-degree per edge type (configurable in `MAX_OUT_DEGREE`)
- Confidence floors per edge type (configurable in `CONFIDENCE_FLOORS`)
- Density cap: total ≤ 4× node count

## Key Files

| File | Role |
|------|------|
| [cross_source.py](../../backend/services/graph_service/cross_source.py) | Core linker: mention detection, semantic edges, intra-file, pruning |
| [builder.py](../../backend/services/graph_service/builder.py) | Rebuild pipeline — Pass 11 invokes `rebuild_cross_source_edges` |
| [chunking.py](../../backend/services/chunking.py) | `subject_kind` parameter for per-type section weighting |
| [embedding_service.py](../../backend/services/embedding_service.py) | `subject_type` parameter on `embed_note_chunks` |
| [database.py](../../backend/models/database.py) | `note_chunks.subject_type` column + migration |
| [graph.py](../../backend/routers/graph.py) | `POST /api/graph/rebuild-cross-source` endpoint |
| [test_cross_source.py](../../backend/tests/test_cross_source.py) | 15 tests (pure + integration) |

## API

### `POST /api/graph/rebuild-cross-source`

Rebuilds only cross-source and intra-file edges without a full graph
rebuild.  Returns `{"status": "ok", "edges_added": N}`.

## Gotchas

- `about_same_topic_as` requires ≥ 1 shared canonical entity on top of
  high chunk similarity, specifically to avoid connecting unrelated items
  that happen to share common words (e.g. "onboarding").
- Intra-file edges only fire on long subjects (> 8 chunks), and only
  between distant chunks, to avoid noise.
- The chunk pair computation caps at 300 chunks per subject (reservoir
  sample) and 20 pairs per subject pair for performance.
