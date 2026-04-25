# Step 27 — Graph Density for Long Documents

> **Goal**: After ingesting a handful of large PDFs (100+ MB total), the
> knowledge graph collapses into one "rosette" per file: a single
> `note:` hub with ~80 satellite entities and almost no bridges between
> documents. This step makes long-form ingest produce a **real network**
> instead of disconnected stars.

**Status**: ⬜ Planned
**Depends on**: Step 22e (cross-source linking), Step 25 (Smart Connect),
Step 27 sub-step concepts (TF-IDF pass already in `graph_service/concepts.py`)
**Effort**: ~1 day backend (no schema changes, no migration)

---

## Why this step exists

Reproducible repro (April 2026):
- Reset workspace, ingest 4 PDFs (~100 MB total): HAI AI Index 2025,
  OWASP LLM Top-10, NIST AI RMF, Survey of LLMs.
- Resulting graph: **326 nodes / 732 edges**, four disconnected rosettes
  joined by ~3 thin concept edges.

Root causes (verified against current code):

1. **One PDF = one `note:` node.** `services/ingest.py::fast_ingest`
   writes the entire extracted text to a single Markdown file.
   `graph_service/builder.py` then emits exactly one `note:` node per
   file, regardless of size. A 500-page paper and a 1-page memo have
   the same graph footprint.
2. **Hard caps on per-note entity count.**
   `graph_service/entity_edges.py` clips at
   `MAX_PERSONS_PER_NOTE=50`, `MAX_ORGS_PER_NOTE=50`, etc., and at
   `_MAX_CO_MENTION_PAIRS_PER_NOTE=100`. Long-tail entities from
   400-page documents are silently dropped.
3. **Concept pass is brittle on mixed PL/EN corpora.** TF-IDF in
   `graph_service/concepts.py` works, but its bigram filter and
   stopword list miss enough noise that real cross-document bridges
   are crowded out by per-document idiosyncrasies.

The result is a graph that looks busy locally but has almost no
inter-document structure — exactly the opposite of what a personal
knowledge graph should provide.

---

## Sub-steps

| Sub-step | Title | Status |
|----------|-------|--------|
| [27a](step-27a-pdf-section-split.spec.md) | Split large PDFs into section notes at ingest | ⬜ |
| [27b](step-27b-scaled-entity-limits.spec.md) | Length-scaled entity caps + co-mention caps | ⬜ |
| [27c](step-27c-concept-pass-improvements.spec.md) | Better concept pass: bigram quality, PL/EN normalisation | ⬜ |

**Execution order**: 27a → 27b → 27c. 27a alone closes most of the gap;
27b and 27c are amplifiers.

---

## Acceptance criteria (whole step)

After re-ingesting the same four PDFs from a clean workspace:

- Graph contains **≥ 1500 nodes** and **≥ 4000 edges** (was 326 / 732).
- Each PDF expands into ≥ 5 `note:` nodes (one per top-level section).
- ≥ 30 `concept:` or cross-source edges directly bridge two different
  PDFs (was ~3).
- Re-ingest is idempotent: running the same ingest twice does not
  duplicate notes (filename suffix logic in `_unique_path` covers
  re-ingest of the *same* PDF; section split must be deterministic).
- No regression in any existing test under `backend/tests/`.

---

## Out of scope

- Chunking changes for retrieval (chunks already work; this is about
  graph nodes).
- New node types — sections are plain `note:` nodes in subfolders.
- AI-based section detection — heuristic heading detection only.
- Migration of *existing* workspaces — user re-ingests after pulling
  this change. Documented in CHANGELOG.
