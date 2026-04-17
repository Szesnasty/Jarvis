# Step 22e — Cross-Source Linking & Intra-File Chunk Connections

> **Goal**: Make Jira issues, notes, decisions, PDFs, URL ingests and
> meeting transcripts link to each other at the *fragment* level. Extend
> and generalise the chunk-edge mechanism from step-20c so every source
> type participates. This step is what turns Jarvis from "a better
> grep over my notes" into a context system.

**Status**: ⬜ Not started
**Depends on**: 22b (node types), 22c (enrichment), 22d (soft edges),
step-20a (chunking), step-20c (chunk graph edges), step-20d (entity
canonicalisation)
**Effort**: ~3 days

---

## What exists and what is missing

- 20a chunks notes.
- 20c adds chunk-level graph edges between `note` nodes only.
- 20d canonicalises entities across notes.
- 22b introduces `jira_issue` / `jira_epic` / `jira_sprint` / … nodes.
- **Gap**: chunk linking is not aware of the new node types, is not aware
  of enrichment signals, and does not cross source boundaries
  (issue→decision, PDF→note, URL→issue).

This step widens the chunk-linker to any chunked subject and layers
enrichment signals on top.

---

## Generalisation

Rename the mental model from "note chunk edges" to **subject chunk
edges**. A *chunked subject* is any record that has text and chunks:

```
subject := (type, id, note_path, chunks)
types   := { note, jira_issue, url_ingest, pdf_doc, transcript, decision }
```

All of them already write Markdown. The chunking service (20a) already
runs on Markdown. So the change is:

1. `services/chunking.py` accepts a `subject_kind` hint used for
   section-weighting (titles matter more on `jira_issue`).
2. `note_chunks` table grows a `subject_type` column (default `"note"`
   for back-compat, populated for new rows).
3. The chunk-linker iterates all subjects, not just notes.

---

## New cross-source edge types

All derived, all `source="derived"`, emitted by the extended linker:

| Edge type                          | Endpoints                                | Trigger                                                                 |
|------------------------------------|------------------------------------------|-------------------------------------------------------------------------|
| `mentions_issue`                  | `note \| decision \| url \| pdf → jira_issue` | Wiki-link `[[KEY]]` or regex hit for a known issue_key                  |
| `mentioned_in_note`               | `jira_issue → note`                     | Inverse of above, emitted for the other direction                       |
| `implements_decision`             | `jira_issue → decision`                  | ≥ 2 chunk matches ≥ 0.78 AND enrichment `execution_type=implementation` |
| `derived_from_research`           | `jira_issue → note`                      | ≥ 2 chunk matches ≥ 0.75 AND enrichment `execution_type=investigation` on the note side |
| `about_same_topic_as`             | any chunked subject ↔ any chunked subject | ≥ 2 chunk matches ≥ 0.78 AND ≥ 1 shared canonical entity                |
| `owned_by`                        | `jira_issue → jira_person`              | Already from 22b (hard). Reused here for cross-source personas.         |

"About same topic" is the cross-source generalisation of the same edge
from 22d. When both endpoints are Jira issues it collapses to the 22d
rule; when they straddle sources, the entity overlap guard raises
precision sharply — avoids connecting a stray onboarding note to every
single `onboarding` issue.

---

## Linker algorithm

```
for each candidate pair (A, B) in ANN top-K on node embeddings:
    if A.subject_type == B.subject_type and A is a note/issue:
        # already handled by 22d or 20c
        continue
    chunk_matches = top_k_chunk_pairs(A, B, k=5, floor=0.70)
    shared_entities = canonical_entities(A) ∩ canonical_entities(B)
    enrichment_bias = enrichment_compatibility(A, B)   # see below
    if gate(edge_type, chunk_matches, shared_entities, enrichment_bias):
        emit(edge_type, A→B, confidence=f(...), evidence=chunk_matches)
```

`enrichment_compatibility` is a small lookup:

- `investigation` (note) ↔ `implementation` (issue) → +0.10 toward `derived_from_research`.
- `decision` (note) ↔ `implementation` (issue) → +0.10 toward `implements_decision`.
- Same `business_area` on both sides → +0.05 on `about_same_topic_as`.
- Mismatched `business_area` → −0.10 (strong signal against spurious links).

All increments are documented in a table in code and unit-tested.

---

## Intra-file chunk connections

Inside a single large file (e.g. a 30-page PDF or a long meeting
transcript), chunk-to-chunk edges tell retrieval "these sections belong
together even though the user's query hits only one". New intra-file
edge type:

- `same_document_thread` — between chunks `(i, j)` in the same subject
  where `cosine(chunk_i, chunk_j) ≥ 0.80` AND `|i - j| ≥ 3`. Limited to
  top-3 per chunk. Used by the retrieval rebalancer (22f) to expand a hit
  to neighbouring thematic chunks, not just adjacent ones.

This runs opportunistically on long subjects only (`> 8 chunks`) to
control cost.

---

## Performance

Candidate explosion is the enemy. Hard caps:

- Global: ANN top-K = 40 per node.
- Per edge type: max 8 out-edges per node.
- Chunk-pair computation limited to top-20 pairs per subject pair.
- For subjects with `len(chunks) > 300` (huge PDFs), sample 300 chunks
  by TF-IDF-weighted reservoir — full coverage is unnecessary.

Memory target: rebuild on a 2 000-subject / 50 000-chunk workspace must
stay under 1.5 GB RSS.

---

## Rebuild orchestration

A single command rebuilds everything in order:

```
POST /api/graph/rebuild-all
  → 1. chunking (new/changed subjects only)
    2. subject + chunk embeddings (new/changed only)
    3. entity extraction + canonicalisation
    4. enrichment catch-up (bounded)
    5. jira projection (22b)
    6. soft edges (22d)
    7. cross-source edges (this step)
    8. prune
    9. write graph.json + bump version
```

Each stage emits SSE progress; stages 1–3 are incremental, stages 5–7
are full rebuilds scoped by `source="derived"` + `source="jira"`.

---

## Tests

- `test_mentions_issue_direct`: note contains `[[ONB-142]]` → edge to
  the issue node, reverse edge too.
- `test_implements_decision_gate`: matching chunks but wrong
  `execution_type` → no edge.
- `test_cross_type_entity_gate`: two subjects with high cosine but zero
  shared canonical entities → no `about_same_topic_as` edge.
- `test_intra_file_edges_only_long`: short note → no `same_document_thread`.
- `test_rebuild_scales`: synthetic 2 000-subject workspace rebuilds
  inside the memory target (tag: `slow`).

---

## Definition of done

- After import + rebuild, clicking a Jira issue in the graph UI reveals
  the decision notes, meeting notes and prior issues that relate to it.
- Asking *"what did we decide about X?"* returns a context that includes
  the decision note AND the tickets linked to it (wired by 22f).
- Rebuild is deterministic and bounded in memory.
- `docs/features/cross-source-linking.md` authored.
