# Step 28d — Section Type Classification

> **Goal**: Tag every section note produced by Step 27 with a
> `section_type` (e.g. `requirements`, `risks`, `integrations`),
> stored in frontmatter. Retrieval can then prefilter by type when
> the user asks a typed question (*"what risks does this RFP
> mention?"*) instead of relying purely on text similarity.

**Parent**: [step-28-document-intelligence.md](step-28-document-intelligence.md)
**Status**: ✅ Done
**Depends on**: 28a (visibility), 28c (baseline numbers must exist
*before* this lands)

---

## Why

Section split was a structural win — the graph now sees a 400-page
RFP as a cluster, not a hub. But retrieval still treats every section
as text-of-equal-shape. A question about *risks* competes against a
section titled "Project Scope" purely on token overlap. With typed
sections, the intent parser can prefer matching types and only fall
back to similarity when no typed section is competitive.

Two non-obvious constraints from prior decisions:

1. **No new graph node types.** Step 27 cleanup
   ([commit dbe2ca9](https://github.com/.../commit/dbe2ca9)) just
   removed generic `imported / pdf / section` tags from frontmatter
   and stored them as `source_type` instead, *to stop them creating
   hub nodes in the graph*. Adding `concept:risks` would re-introduce
   exactly that anti-pattern. **Frontmatter field only.**
2. **Mixed PL/EN corpora.** Step 27c improved the concept pass for
   this. Classifier signals must work on both languages.

---

## Design

### Taxonomy

A small fixed set of types. New types require a code change, not a
config edit — keeps drift bounded:

```
requirements         "must", "shall", "system should"
risks                "risk", "threat", "vulnerability", "ryzyko"
integrations         "API", "webhook", "integration", "integracja"
security             "auth", "encryption", "access control", "RBAC"
timeline             "milestone", "deadline", "phase", "harmonogram"
pricing              "cost", "budget", "pricing", "wycena"
stakeholders         "stakeholder", "team", "owner", "responsible"
open_questions       "TBD", "unclear", "to confirm", "do ustalenia"
technical_constraints  "must support", "limitation", "constraint"
business_goals       "objective", "goal", "KPI", "cel"
front_matter         (always front-matter section from 27a)
other                fallback
```

### Two-stage classifier

**Stage 1 — heuristic, cheap.** Runs over the section body in pure
Python. Returns `(type, confidence, signals)`:

- Tokenise body, lowercase, strip diacritics for PL.
- Score each type by weighted keyword count / words ∈ [0, 1].
- Add a heading-level prior: `^Risks?$`, `^Wymagania$`, `^Cennik$`,
  `^Integracje$` → strong prior on the matching type (+0.4 to its
  score, capped at 1.0).
- If the top type's score ≥ 0.6 *and* its margin over second place
  ≥ 0.15 ⇒ accept. Confidence = top score.
- Otherwise return `(other, top_score, signals)` — Stage 2 will
  re-decide.

**Stage 2 — LLM fallback.** Only for sections where Stage 1 returned
`other` *or* confidence < 0.6. Sends ~500 chars (head of section
body) + the heading to a small Claude call (Haiku — fast and cheap)
and asks for one of the taxonomy labels. Result cached per
section path so re-classification is free on subsequent runs.

For a 12-section PDF with strong headings, Stage 1 typically catches
8–10. Stage 2 makes ≤ 4 small calls per document. Estimated cost:
~$0.001 per PDF.

### Where it runs

`backend/services/document_classifier.py` (new). Two public
functions:

```python
def classify_section_heuristic(
    title: str, body: str
) -> tuple[str, float, dict]: ...

async def classify_section_llm(
    title: str, body: str, anthropic_client
) -> tuple[str, float]: ...
```

Hook into [ingest.py `_emit_pdf_sections`](../../backend/services/ingest.py)
right before writing each section file:

```python
stype, conf, signals = classify_section_heuristic(title, body)
if stype == "other" or conf < 0.6:
    stype, conf = await classify_section_llm(title, body, client)
fm = {
    "title": title,
    "parent": index_path,
    "section_index": idx,
    "section_type": stype,
    "section_type_confidence": round(conf, 2),
    # signals omitted from frontmatter (debug-only, kept in logs)
}
```

`section_type` is `Optional[str]` — sections from non-PDF or
pre-Step-28d ingests have no field, retrieval treats absent as
unfiltered.

### Retrieval prefilter

In [intent_parser.py](../../backend/services/retrieval/intent_parser.py),
detect typed-question intent:

```
"what risks…"      → preferred_section_types=["risks"]
"jakie ryzyka…"    → preferred_section_types=["risks"]
"timeline / harmonogram" → ["timeline"]
"co dokument mówi o integracjach" → ["integrations"]
```

In `pipeline.py`, when `preferred_section_types` is non-empty and a
candidate's `section_type` is in that set, add a small fused boost
(0.10 × matched, capped). Do **not** filter out non-matching
candidates — boost only. This preserves recall for queries the
classifier or the heading detector got wrong.

### Backfill

A one-shot script `backend/scripts/classify_existing_sections.py`
walks the workspace, finds notes with `parent` set (i.e. emitted
sections), and re-runs the classifier. Frontmatter is updated
in-place via `parse_frontmatter` / `add_frontmatter` (existing
helpers). Idempotent: if `section_type` exists and confidence ≥ 0.7
the script skips.

---

## Code changes

| File | Change |
|------|--------|
| `backend/services/document_classifier.py` (new) | Heuristic + LLM stages. |
| [backend/services/ingest.py](../../backend/services/ingest.py) | `_emit_pdf_sections` writes `section_type` + confidence. |
| [backend/services/retrieval/intent_parser.py](../../backend/services/retrieval/intent_parser.py) | Detect typed-question intent (PL+EN). |
| [backend/services/retrieval/intent.py](../../backend/services/retrieval/intent.py) | Add `preferred_section_types: list[str]` to `QueryIntent`. |
| [backend/services/retrieval/pipeline.py](../../backend/services/retrieval/pipeline.py) | Apply the boost when set. |
| `backend/scripts/classify_existing_sections.py` (new) | Backfill. |

---

## Tests

- `backend/tests/test_document_classifier.py`:
  1. Heading "Ryzyka" + body about threats ⇒ `risks` with confidence ≥ 0.7.
  2. Generic "Introduction" ⇒ `other` from Stage 1, deferred to LLM.
  3. Score margin too small ⇒ Stage 2 invoked.
  4. PL/EN mix in body still produces correct type for clear cases.
- `backend/tests/test_intent_parser_section_types.py`:
  1. "what risks…" → `preferred_section_types=["risks"]`.
  2. "jakie wymagania ma klient" → `["requirements"]`.
  3. Generic question ("summarize this document") → empty list.
- `backend/tests/test_pipeline_section_type_boost.py`:
  1. Boost applied only when intent type matches candidate type.
  2. Boost is additive, capped, never filters out non-matching
     candidates.
- **Eval delta**: re-run 28c baseline. Mean Recall@5 on
  `section_typed` bucket must improve by **≥ 8 percentage points**;
  no other bucket may regress by more than 2 points. This is the
  step's binary acceptance criterion.

---

## Acceptance

- Re-ingesting the four reference PDFs assigns `section_type` to
  every section. ≥ 80% of sections classified by Stage 1 alone.
- Asking *"what risks does the OWASP doc list?"* surfaces a
  `section_type: risks` section in the top 3, where pre-28d it was
  outside top 5 (verified against 28c baseline).
- Backfill script run on an existing workspace updates all section
  notes in-place with no graph rebuild required (frontmatter changes
  alone; graph is not affected).

---

## Out of scope

- Multi-label classification (a section is exactly one type).
- Editing taxonomy from the UI.
- Showing `section_type` in the Memory sidebar (28b's tree row already
  shows tags; this can read frontmatter later, not part of 28d).
- Section-typed nodes in the graph — explicitly forbidden, see Why.
- Per-user custom types — bounded taxonomy is a feature.
