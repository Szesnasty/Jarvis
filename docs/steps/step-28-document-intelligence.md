# Step 28 — Document Intelligence & Retrieval Trust

> **Goal**: Step 27 split large PDFs into per-section notes. Now we need
> three things on top: (1) **see** which sections actually drive every
> answer, (2) **read** the split documents without losing the Memory
> sidebar to a wall of fragments, (3) **measure** whether downstream
> changes improve retrieval quality. With those in place, document
> intelligence (section typing) and a real business workflow (client
> estimate) become defensible additions instead of guesswork.

**Status**: ✅ Done
**Depends on**: Step 27 (PDF/text section split — landed in Phase 19)
**Effort**: ~4–5 days backend + frontend, no schema migration

---

## Why this step exists

After Phase 19 a single 400-page PDF expands into 1 index note + N section
notes with `parent`, `section_index`, and `document_type: pdf-document`
in frontmatter. This unlocked graph density but introduced three
follow-on problems verified against current code:

1. **Retrieval is opaque to the user.** [pipeline.py:815](../../backend/services/retrieval/pipeline.py#L815)
   already attaches a `_signals` dict (BM25 / cosine / graph /
   enrichment / boost) to each candidate, and
   [context_builder.py:557-565](../../backend/services/context_builder.py#L557-L565)
   tags graph-expansion notes with `via=`/`tier=` attributes that flow
   into the Claude prompt. None of it reaches the UI — users cannot
   tell whether section split actually improved answers or just
   produced more clutter.
2. **The Memory sidebar collapses under a 50-section paper.** The flat
   list in [NoteList.vue:54-79](../../frontend/app/components/NoteList.vue#L54-L79)
   renders one row per section. Four reference PDFs ⇒ ~50 rows of
   indistinguishable section titles before the user's own notes appear.
3. **Quality changes are unmeasured.** A harness exists
   ([tests/eval/runner.py:13-46](../../backend/tests/eval/runner.py#L13-L46))
   with Recall / MRR / Precision@K, but its corpus is synthetic
   ([tests/eval/corpus.py](../../backend/tests/eval/corpus.py)) — there
   are no reference queries against the actual split-document corpus
   that Step 27 introduced.

Once those three are in place, two further additions become high-value
and low-risk: **section classification** (so retrieval can prefer
`section_type=risks` for a question about risks) and a **Client
Estimate specialist** (the first concrete business workflow that
exploits per-section retrieval).

---

## Sub-steps

| Sub-step | Title | Status |
|----------|-------|--------|
| [28a](step-28a-retrieval-trace-ui.spec.md) | Retrieval Trace UI — surface `_signals` and graph-expansion provenance per chat answer | ✅ |
| [28b](step-28b-memory-document-grouping.spec.md) | Memory document grouping — collapse split documents into one expandable parent in the sidebar | ✅ |
| [28c](step-28c-eval-baseline.spec.md) | Eval baseline against the four reference PDFs — frozen query set + reproducible run script | ✅ |
| [28d](step-28d-section-classification.spec.md) | Section type classification (heuristic + LLM fallback) and a retrieval filter that exploits it | ✅ |
| [28e](step-28e-client-estimate-specialist.spec.md) | Client Estimate specialist — first business workflow on top of section-typed retrieval | ✅ |

**Execution order**: 28a → 28b → 28c → 28d → 28e.

The order is not negotiable for two reasons:

- **28a before everything**: without trace UI the user cannot see
  whether 28d/28e are actually helping. Doing 28d before 28a means
  shipping changes blind.
- **28c before 28d/28e**: 28c freezes the baseline numbers *before*
  any retrieval-affecting change. Running it after means we cannot
  attribute any delta to 28d.

28b sits in slot 2 because it is independent of the retrieval stack
and removes the visual blocker the user already lives with daily.

---

## Acceptance criteria (whole step)

- After every chat answer the UI shows a collapsible "Used context"
  panel listing each note that fed the prompt with its top signal
  (e.g. `bm25=0.71`, `via=related, tier=strong`).
- Memory sidebar renders one collapsible row per ingested document:
  e.g. `▸ HAI AI Index Report 2025 (12 sections)`. Singleton notes
  remain flat.
- `pytest backend/tests/eval/test_eval_baseline.py -v` runs against
  the four reference PDFs and writes a baseline JSON to
  `backend/tests/eval/baselines/step-28c.json` checked into git.
- Every section note carries `section_type` in frontmatter with a
  `confidence` value. Retrieval prefilter uses it for risk /
  requirement / integration questions.
- A built-in `client-estimator` specialist exists in
  `Jarvis/agents/` after first run; activating it in the UI produces
  a structured brief (Goals / Scope / Risks / …) sourced from the
  current workspace's split documents.
- All existing tests under `backend/tests/` and `frontend/test/`
  continue to pass.

---

## Out of scope

- Re-ranking the BM25 / cosine / graph fusion weights. 28a only
  *reports* what the pipeline already computes.
- Persisting trace data — traces are computed per-request and shown
  inline; no new SQLite table.
- Full document-type taxonomy for non-PDF sources. 28d focuses on
  PDF-derived sections; other sources keep current behaviour.
- A specialist marketplace or templating system. 28e ships exactly
  one built-in specialist as the proof point.
- Automatic specialist routing. The user activates `client-estimator`
  manually, matching the current MVP usage model.
- Migration of pre-Step-27 workspaces. Users who never re-ingested
  after Phase 19 still see old single-file documents; 28b degrades
  gracefully (no `document_type` ⇒ flat row).
