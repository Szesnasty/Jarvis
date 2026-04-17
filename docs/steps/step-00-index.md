# Implementation Steps — Index

> **Guidelines**: Follow [CODING-GUIDELINES.md](../CODING-GUIDELINES.md) for all code.
> **Full plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)

---

## Phase 1 — System Skeleton

| Step | Title | Status |
|------|-------|--------|
| [01](step-01-backend-init.md) | Backend initialization (FastAPI) | ✅ |
| [02](step-02-frontend-init.md) | Frontend initialization (Nuxt 3) | ✅ |
| [03](step-03-onboarding-workspace.md) | Onboarding + workspace creation | ✅ |

## Phase 2 — Local Memory

| Step | Title | Status |
|------|-------|--------|
| [04](step-04-memory-service.md) | Memory service + SQLite index | ✅ |

## Phase 3 — Claude API

| Step | Title | Status |
|------|-------|--------|
| [05](step-05-claude-integration.md) | Claude API + streaming + tools | ✅ |

## Phase 4 — Voice

| Step | Title | Status |
|------|-------|--------|
| [06](step-06-voice.md) | Voice input/output + states | ✅ |

## Phase 5 — Planning & Operational Memory

| Step | Title | Status |
|------|-------|--------|
| [07](step-07-planning-ops.md) | Planning tools + session persistence | ✅ |

## Phase 6 — Knowledge Graph

| Step | Title | Status |
|------|-------|--------|
| [08](step-08-knowledge-graph.md) | Graph model + visualization + retrieval | ✅ |

## Phase 7 — Specialists

| Step | Title | Status |
|------|-------|--------|
| [09](step-09-specialists.md) | Specialist system + UI wizard | ✅ |

## Phase 8 — Polish

| Step | Title | Status |
|------|-------|--------|
| [10](step-10-polish.md) | UI polish, Obsidian, caching, ingest | ✅ |

## Phase 9 — URL Ingest

| Step | Title | Status |
|------|-------|--------|
| [11](step-11-url-ingest.md) | URL ingest pipeline (YouTube + Web) | ✅ |
| [11b](step-11b-url-ingest-frontend.md) | URL ingest frontend (dialog + chat) | ✅ |

## Phase 10 — Graph Intelligence + Living Memory

> **Execution order**: 14a → 15 → 14b → 16a → 16b → 17
> Feedback loops before graph refinement — bigger user impact first.

| Step | Title | Status | Order |
|------|-------|--------|-------|
| [12](step-12-graph-interactive.md) | Interactive graph UX (preview, ask, filter, orphans, manual edges) | ✅ | — |
| [13](step-13-graph-retrieval.md) | Graph-guided retrieval (weighted edges, IDF, path scoring) | ✅ | — |
| [14a](step-14a-entity-extraction.md) | Entity extraction + bidirectional wiki-links | ✅ | → 1st |
| [15](step-15-feedback-loops.md) | Feedback loops (auto-graph, attribution, session→memory, realtime refresh) | ✅ | → 2nd |
| [14b](step-14b-graph-refinement.md) | Similarity edges, temporal edges, pruning, rebuild pipeline | ✅ | → 3rd |

## Phase 11 — Duel & Council Mode

| Step | Title | Status | Order |
|------|-------|--------|-------|
| [16a](step-16a-duel-backend.md) | Duel Mode backend (orchestrator, prompts, scoring, WS events, memory save) | ✅ | → 4th |
| [16b](step-16b-duel-frontend.md) | Duel Mode frontend (setup, debate view, score bar, chat integration) | ✅ | → 5th |
| [17](step-17-council-full.md) | Council Full (3-4 specialists, compression, alliance map, learning extraction) | ⬜ | v2 |

## Phase 12 — Multi-Provider LLM Support

| Step | Title | Status |
|------|-------|--------|
| [18a](step-18a-multi-provider-keys-frontend.md) | Multi-provider API keys: frontend (browser storage, Settings UI, provider cards) | ✅ |
| [18b](step-18b-multi-provider-backend.md) | Multi-provider backend: LiteLLM integration (unified streaming, per-request keys) | ✅ |
| [18c](step-18c-model-selector.md) | Model selector UI + per-specialist model config + persistence | ✅ |
| [18d](step-18d-onboarding-multi-provider.md) | Onboarding redesign: multi-provider welcome flow + keyless workspace init | ✅ |

## Phase 13 — Semantic Search & Hybrid Retrieval

> **Execution order**: 19a → 19b → 19c
> Fix BM25 first (free win), then add embeddings, then wire everything together.

| Step | Title | Status | Order |
|------|-------|--------|-------|
| [19a](step-19a-fts5-bm25-ranking.md) | Fix FTS5 BM25 ranking (column weights, OR fallback, real scores) | ✅ | → 1st |
| [19b](step-19b-local-embedding-service.md) | Local embedding service (fastembed, SQLite storage, embed on write) | ✅ | → 2nd |
| [19c](step-19c-hybrid-retrieval-graph-semantic.md) | Hybrid retrieval + graph-semantic integration (3-signal fusion, semantic edges) | ✅ | → 3rd |

## Phase 14 — Semantic Node Connection

> **Execution order**: 20f (baseline) → 20a → 20b → 20c ∥ 20d → 20e → 20f (re-run)
> Establish eval baseline first. Chunking is the foundation. Entity canonicalization
> runs in parallel with semantic anchors + chunk graph edges.

| Step | Title | Status | Order |
|------|-------|--------|-------|
| [20-overview](step-20-semantic-overview.md) | Semantic Node Connection: overview + architecture | ✅ | — |
| [20f](step-20f-eval-set.spec.md) | Evaluation benchmark (50 queries, baseline metrics) | ✅ | → 1st |
| [20a](step-20a-chunking.spec.md) | Chunk-level embeddings (heading split + sliding window) | ✅ | → 2nd |
| [20b](step-20b-semantic-anchors.spec.md) | Semantic graph anchors + node embeddings | ✅ | → 3rd |
| [20c](step-20c-chunk-graph-edges.spec.md) | Chunk-level graph linking with evidence | ✅ | → 4th |
| [20d](step-20d-entity-canonicalization.spec.md) | Entity deduplication + alias table | ✅ | → 4th ∥ |
| [20e](step-20e-retrieval-rebalance.spec.md) | Retrieval rebalance + chunk-aware context | ✅ | → 5th |
| [20g](step-20g-graph-evidence-ui.spec.md) | Graph evidence UI: edge tooltips + chunk preview | ✅ | → 6th |

## Phase 15 — Local Models (Ollama)

> **Execution order**: 21a → 21b → 21c → 21d
> Backend first, then Settings UI, then onboarding flow, then integration polish.

| Step | Title | Status | Order |
|------|-------|--------|-------|
| [21a](step-21a-local-models-backend.spec.md) | Local models backend: Ollama service, hardware probe, model catalog, API | ✅ | → 1st |
| [21b](step-21b-local-models-frontend.spec.md) | Local models frontend: Settings UI, model cards, pull progress, ModelSelector | ✅ | → 2nd |
| [21c](step-21c-local-models-onboarding.spec.md) | Local models onboarding: Cloud vs Local choice, keyless workspace creation | ✅ | → 3rd |
| [21d](step-21d-local-models-integration.spec.md) | Local models integration: tool calling, timeouts, health monitoring, warm-up | ✅ | → 4th |

## Phase 16 — Jira as First-Class Knowledge + Cross-Source Context

> **Execution order**: 22a → 22b → 22c ∥ 22d → 22e → 22f → 22g
> Ingest first, then projection, then local-model enrichment and soft edges
> in parallel, then cross-source linking, retrieval, specialist.

| Step | Title | Status | Order |
|------|-------|--------|-------|
| [22-overview](step-22-jira-knowledge-overview.md) | Jira knowledge layer: overview + architecture + gap analysis | ✅ | — |
| [22a](step-22a-jira-ingest.spec.md) | Jira XML/CSV streaming ingest + `issues` table + Markdown emission | ✅ |→ 1st |
| [22b](step-22b-jira-entities-graph.spec.md) | Jira node types + explicit (hard) graph edges | ✅ | → 2nd |
| [22c](step-22c-local-enrichment.spec.md) | Local-model enrichment pipeline (classification / risk / ambiguity / summary) | ✅ | → 3rd |
| [22d](step-22d-soft-edges.spec.md) | Soft edges (same_topic / likely_dependency / business_area) with confidence | ✅ | → 3rd ∥ |
| [22e](step-22e-cross-source-linking.spec.md) | Cross-source linking: issue ↔ note / decision / doc, intra-file chunk edges | ✅ | → 4th |
| [22f](step-22f-jira-retrieval.spec.md) | Jira-aware hybrid retrieval with facets, boosts and structured context | ⬜ | → 5th |
| [22g](step-22g-jira-strategist.spec.md) | `Jira Strategist` specialist + sprint/blocker tools + Duel presets | ⬜ | → 6th |

---

## Execution Rule

Complete each step fully before moving to the next.
**Prefer a working vertical slice over broad scaffolding.**
