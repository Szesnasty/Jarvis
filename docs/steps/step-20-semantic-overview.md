# Step 20 — Semantic Node Connection: Overview

> **Goal**: Transform Jarvis from note-level embeddings + substring graph anchors
> into a chunk-level, semantically-native knowledge system where retrieval,
> graph linking, and entity resolution all operate on meaning — not just keywords.

**Status**: ⬜ Not started
**Branch**: `feat/semantic-node-connection`
**Depends on**: Steps 19a–19c (BM25, embeddings, hybrid retrieval — all implemented)

---

## Current State (honest audit)

| Layer | What exists today | Limitation |
|-------|-------------------|------------|
| Embeddings | One vector per note (`title+title+tags+body`) | Long notes → diluted meaning; no section-level precision |
| Vector search | Brute-force `SELECT * FROM note_embeddings` + cosine loop | O(n) scan, no index; fine for <1000 notes, won't scale |
| Retrieval | BM25-first candidates, cosine + graph as correction signals | Semantic isn't a first-class citizen — it's an additive boost |
| Graph anchors | `node.label.lower() in query_lower` for person/tag/area only | Leksykalny substring match; misses synonyms, typos, semantic equivalence |
| Graph edges | `similar_to` between **notes** at cosine ≥ 0.65, max 5/node | Note-level granularity; no chunk evidence; no typed relations |
| Entity extraction | Regex-based person/date/project extraction | No canonicalization; "Sam Altman" vs "Altman" = two different entities |

### Key files involved

| File | Lines | Role |
|------|-------|------|
| `backend/services/embedding_service.py` | 205 | Embed notes, search similar, blob serialization |
| `backend/services/retrieval.py` | 302 | Hybrid BM25+cosine+graph fusion |
| `backend/services/graph_service.py` | 718 | Graph CRUD, rebuild, similarity edges, scoring |
| `backend/services/entity_extraction.py` | 99 | Regex entity extraction |
| `backend/services/context_builder.py` | 250 | Build prompt context from retrieval results |
| `backend/services/memory_service.py` | 409 | Note CRUD, indexing, embedding trigger |
| `backend/models/database.py` | 115 | SQLite schema: notes, notes_fts, note_embeddings |
| `backend/services/ingest.py` | 183 | File import pipeline |

---

## Target Architecture

```
User query
    │
    ├─── embed query ──────────────────┐
    │                                   │
    ▼                                   ▼
┌──────────────┐              ┌────────────────────┐
│ BM25 Search  │              │  Chunk ANN Search  │
│ (FTS5 on     │              │  (chunk_embeddings │
│  full notes) │              │   cosine top-K)    │
└──────┬───────┘              └─────────┬──────────┘
       │                                │
       ▼                                ▼
  note candidates               chunk candidates
       │                                │
       └────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │   Semantic Graph Anchoring        │
    │                                   │
    │   query embedding vs node         │
    │   embeddings → top-K anchors      │
    │   (replaces substring match)      │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │   Graph Scoring                   │
    │   (path distance + edge weight    │
    │    + cluster bonus)               │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │   Weighted Fusion                 │
    │   BM25 0.25 + Chunk 0.40 + G 0.35│
    │   (rebalanced for chunk signal)   │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │   Parent Note Aggregation         │
    │   chunk scores → note ranking     │
    │   best chunk as snippet           │
    └───────────────┬───────────────────┘
                    │
                    ▼
              Final results
```

---

## Sub-steps

| Step | File | Title | Effort | Risk |
|------|------|-------|--------|------|
| 20a | `step-20a-chunking.spec.md` | Chunk-level embeddings | 2d | Low — additive, no breaking changes |
| 20b | `step-20b-semantic-anchors.spec.md` | Semantic graph anchors + node embeddings | 1d | Low — replaces substring match |
| 20c | `step-20c-chunk-graph-edges.spec.md` | Chunk-level graph linking with evidence | 1.5d | Medium — changes graph edge model |
| 20d | `step-20d-entity-canonicalization.spec.md` | Entity deduplication + alias table | 1.5d | Low — additive |
| 20e | `step-20e-retrieval-rebalance.spec.md` | Retrieval rebalance + chunk-aware context | 1d | Low — weight tuning + context builder |
| 20f | `step-20f-eval-set.spec.md` | Evaluation benchmark (50 queries) | 1d | None — test-only |
| 20g | `step-20g-graph-evidence-ui.spec.md` | Graph evidence UI: edge tooltips + chunk preview | 0.5d | Low — frontend-only, backwards compatible |

**Total estimated effort**: ~8.5 working days

### Dependency graph

```
20a (chunking)
 ├──→ 20b (semantic anchors)  — needs node embeddings infrastructure from 20a
 ├──→ 20c (chunk graph edges) — needs chunk_embeddings table from 20a
 │     └──→ 20g (graph evidence UI) — needs evidence metadata from 20c
 └──→ 20e (retrieval rebalance) — needs chunk search from 20a
20d (entity canon.) — independent, can run in parallel with 20b/20c
20f (eval set) — should start BEFORE 20a to establish baseline
```

**Recommended execution order**: 20f (baseline) → 20a → 20b → 20c ∥ 20d → 20e → 20g → 20f (re-run)

---

## What we are NOT doing (and why)

| Omitted | Reason |
|---------|--------|
| Cross-encoder reranker | Adds ~300MB RAM model; marginal gain at <50 candidates; revisit when chunk pool is large |
| Parallel retrieval with RRF fusion | Current sequential pipeline is debuggable; weight rebalance suffices after chunking |
| Query rewriting / HyDE | Adds API latency per query; voice-first app needs low latency |
| Typed semantic relations (supports/contradicts/explains) | Requires LLM classification per pair; add as optional "smart enrich" later |
| Vector DB migration (Qdrant/FAISS) | Brute-force is fine for <10K chunks; sqlite-vec when needed |
| Personalized PageRank | Graph is too small (<1000 nodes) for PPR to beat BFS path scoring |

---

## Guiding Principles

1. **Markdown is source of truth** — chunks, chunk_embeddings, node_embeddings are derived/rebuildable
2. **No new API calls for core path** — all embeddings stay local (fastembed)
3. **Backwards compatible** — old `note_embeddings` stays; new tables are additive
4. **Graceful degradation** — if chunking unavailable, falls back to note-level embeddings
5. **Measurable** — eval set proves each step helps before merging
