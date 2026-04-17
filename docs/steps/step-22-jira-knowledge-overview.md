# Step 22 — Jira as First-Class Knowledge + Cross-Source Context Layer

> **Goal**: Turn Jarvis into a system that understands *work* — Jira tasks,
> their classification, dependencies and their connection to notes, decisions,
> people, documents and code. Keep the current embedding stack, but add a
> local-model enrichment layer that produces strong, high-confidence links
> between files, between fragments inside files, and between Jira and the
> rest of the workspace.
>
> **Scope note**: Large XML/CSV exports from Jira are the primary driver, but
> every enrichment and linking capability built here must generalise to other
> sources (Markdown notes, PDFs, URL ingest, meeting transcripts).

**Status**: ⬜ Not started
**Depends on**: 19b (embeddings), 20a/b/c/d/e (chunking + semantic graph), 21a–d (local models)
**Philosophy**: Local-first, deterministic where possible, idempotent, rebuildable.

---

## 1. Why this matters

Today Jarvis stores everything as flat Markdown with cosine/BM25/graph fusion.
That is strong for free-form notes, but weak for *structured work items*:

- A Jira issue has a `status`, a `sprint`, an `assignee`, a `priority`,
  `blocked_by` links — none of which survive a naive Markdown dump.
- A Jira export is often 50–500 MB of XML or a 200k-row CSV. Treating it
  like a `.md` note destroys both performance and semantic quality.
- The real value is not storing the tickets but **connecting them** to
  meeting notes, decisions, people and prior issues.

After this phase, Jarvis should be able to answer:

- *"What is actually blocking onboarding this sprint?"*
- *"Which tickets are about the same problem, even if named differently?"*
- *"Which decisions from my notes produced which tickets?"*
- *"Which tasks are under-specified and high risk?"*

---

## 2. Gap analysis vs. current codebase

| Area | Today | Gap |
|---|---|---|
| File formats | `.md`, `.txt`, `.pdf` (`services/ingest.py`) | No XML, no CSV, no streaming |
| Structured items | Every entity becomes a note | No `issues` table, no sprint/status filters |
| Graph node types | `note`, `person`, `tag`, `area` | Missing `jira_issue`, `jira_epic`, `jira_sprint`, `jira_project`, `decision` |
| Explicit relations | Wiki-links, mentions | No `blocks`, `depends_on`, `in_epic`, `in_sprint`, `duplicate_of` |
| Enrichment | Entity extraction only | No classification (`work_type`, `risk`, `ambiguity`) |
| Soft edges | Cosine similarity between chunks | No confidence-weighted `same_topic_as`, no cluster-based edges |
| Retrieval | BM25 + cosine + graph fusion | No facets (status/sprint/assignee/risk), no issue-aware boosts |
| Specialists | Health / Planner etc. | No Jira Strategist profile, no sprint-aware tools |
| Re-sync | One-shot write | No `issue_key`-keyed upsert, no incremental sync |
| Local models | Available via Ollama | Not used for enrichment yet |

---

## 3. Architectural doctrine for this phase

The following rules are binding for all sub-steps:

1. **Markdown is still source of truth.** Every Jira issue produces one
   Markdown file in `memory/jira/{PROJECT}/{KEY}.md`. SQLite tables are a
   rebuildable index on top of those files.
2. **Idempotent upsert by `issue_key`.** Re-importing the same XML/CSV does
   not create duplicates. Changed fields overwrite; unchanged fields are a
   no-op (short-circuit on `content_hash`).
3. **Streaming parser.** XML must be parsed with `xml.etree.ElementTree.iterparse`
   and elements discarded after handling. CSV via `csv.DictReader` with a
   bounded row buffer. Never load a full export into memory.
4. **Enrichment is async, queued and cacheable.** The import path writes the
   raw issue immediately. Classification/risk/ambiguity run in a worker,
   keyed by `(issue_key, content_hash, model_id)` so nothing is recomputed
   for unchanged content.
5. **Two edge families, clearly separated.**
   - **Hard edges** (from Jira itself): `blocks`, `depends_on`, `in_epic`,
     `in_sprint`, `assigned_to`, `duplicate_of`, `parent_of`. Weight ≥ 0.9,
     no TTL.
   - **Soft edges** (derived): `same_topic_as`, `same_business_area_as`,
     `likely_dependency_on`, `implementation_of_same_problem`. Weight =
     confidence ∈ [0,1], stored with `source="derived"` and `generated_at`.
6. **Every derived artefact is rebuildable.** Deleting `jarvis.db` and the
   enrichment cache must be recoverable by re-reading `memory/jira/**`.
7. **Generalised, not Jira-specific.** Classification schemas, enrichment
   pipeline and cross-source linking live in generic services; Jira is the
   first consumer.

---

## 4. Target architecture

```
┌───────────────────────────── Import ─────────────────────────────┐
│ XML stream ──►  jira_ingest.py  ──►  memory/jira/**.md           │
│ CSV stream ──►                   ──►  issues table (SQLite)      │
│                                  ──►  hard edges (graph)         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────── Enrichment queue ────────────────────────┐
│ per-issue worker ── local model (Ollama) ── enrichments table    │
│   • work_type / business_area / execution_type                   │
│   • risk / ambiguity / hidden_concerns                           │
│   • summary + actionable_next_step                               │
│   • likely_dependencies (candidate keys)                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────── Linking pass ────────────────────────────┐
│ chunk embeddings + node embeddings (reuses 20a/20b)              │
│   • issue ↔ issue soft edges                                     │
│   • issue ↔ note / decision / person / doc edges                 │
│   • intra-file chunk-to-chunk edges (generalised 20c)            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────── Jira-aware retrieval ────────────────────┐
│   facets: status / sprint / assignee / risk / business_area      │
│   signals: bm25 + cosine + graph + enrichment match              │
│   shaping: issue boosts, "open only", "this sprint" filters      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────── Specialist + UI ─────────────────────────┐
│ Jira Strategist profile (explain / blockers / sprint risk)       │
│ Duel presets (Delivery Planner vs Risk Analyst, …)               │
│ Sprint view, blocker map                                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Sub-steps

| Step | Title | Status |
|---|---|---|
| [22a](step-22a-jira-ingest.spec.md) | Jira XML/CSV streaming ingest + `issues` table + Markdown emission | ⬜ |
| [22b](step-22b-jira-entities-graph.spec.md) | Jira node types + explicit (hard) graph edges | ⬜ |
| [22c](step-22c-local-enrichment.spec.md) | Local-model enrichment pipeline (classification / risk / ambiguity / summary) | ⬜ |
| [22d](step-22d-soft-edges.spec.md) | Soft edges (same_topic / likely_dependency / business_area) with confidence | ⬜ |
| [22e](step-22e-cross-source-linking.spec.md) | Cross-source linking: issue ↔ note/decision/doc, intra-file chunk edges | ⬜ |
| [22f](step-22f-jira-retrieval.spec.md) | Jira-aware hybrid retrieval with facets and boosts | ⬜ |
| [22g](step-22g-jira-strategist.spec.md) | `Jira Strategist` specialist + sprint/blocker tools + Duel presets | ⬜ |

**Execution order**: 22a → 22b → 22c ∥ 22d → 22e → 22f → 22g.
22c (enrichment) and 22d (soft edges) can run in parallel once 22b lands;
22d depends on enrichment outputs for `business_area`-based edges but can
ship a first version on embeddings alone.

---

## 6. Non-goals for this phase

- Live Jira REST integration (pull directly from Atlassian Cloud). XML/CSV
  exports are the v1 surface. REST is a later step.
- Writing back to Jira (comments, transitions). Read-only.
- Multi-instance / multi-workspace Jira. One Jira export at a time.
- Replacing the generic retrieval pipeline. Jira-awareness is additive.
- Heavy graph DB (Neo4j etc.). We keep the JSON + SQLite model.
- Fine-tuning local models. We only prompt them.

---

## 7. Success metrics

Re-use the step-20f evaluation harness and extend it with:

- **Jira recall@10** on a labelled set of 30 "blocker / related / duplicate"
  triples from the sample export.
- **Enrichment stability**: same issue + same model → identical enrichment
  hash 100 % of the time (cache test).
- **Import throughput**: ≥ 500 issues / minute on a 16 GB Mac, streaming
  memory ≤ 300 MB regardless of export size.
- **Latency impact on retrieval**: issue-aware facets must not add more
  than +50 ms p95 vs. the current baseline.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Huge XML OOM | iterparse + `element.clear()` + batched SQLite inserts |
| Enrichment bill / latency | Cache by `content_hash`; run only on new/changed issues |
| Graph explosion from soft edges | Cap top-k per node; prune below confidence threshold; TTL |
| Re-sync creates duplicates | Unique index on `issue_key`; upsert by key |
| Local model hallucinates classifications | JSON schema validation + retry with lower temperature; unknown → `"unknown"` |
| Jira CSV column drift between instances | Header auto-detection + explicit mapping config per project |
| Cross-source edges to unrelated notes | Confidence threshold + require either ≥ 2 chunk matches or an explicit entity overlap |

---

## 9. What changes for the user

Before: *"ask Jarvis about a file you uploaded"*.
After: *"ask Jarvis about your work"*.

- Drop a Jira XML/CSV export → every issue is searchable and linkable.
- Ask for *blockers*, *risks*, *ambiguity*, *owner* — Jarvis answers from
  local enrichment, not from the raw ticket text.
- Ask *"what did we decide about X?"* — Jarvis links the decision note to
  the tickets that implement it.
- The same enrichment and linking improves the quality of answers over
  notes, PDFs and URL ingests too, because the pipeline is generic.
