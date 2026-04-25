# Step 28e — Client Estimate Specialist

> **Goal**: Ship one built-in specialist that turns a client RFP /
> brief / discovery package into a structured estimate document. It
> exploits 28d section types to assemble each section of the estimate
> from the right typed sections of the source documents.

**Parent**: [step-28-document-intelligence.md](step-28-document-intelligence.md)
**Status**: ⬜ Planned
**Depends on**: 28a (trace), 28b (sidebar), 28c (baseline), 28d
(section types — required for the prefilter approach)

---

## Why

Section split + classification produce a workspace where individual
sections of a 200-page RFP carry semantic types (`risks`,
`requirements`, `integrations`, …). That structure is wasted unless
*something* assembles a workflow on top. A client estimate is the
clearest first business use case: every product team running
discovery does this manually today, the inputs are exactly the
documents Jarvis is now good at, and the output is a single Markdown
file that fits the source-of-truth doctrine.

The specialist system is already built
([specialist_service.py:51-67](../../backend/services/specialist_service.py#L51-L67)).
This step ships *one* configuration plus a thin tool prefilter — it
does not extend the framework.

---

## Design

### Specialist configuration

Built-in specialist at `Jarvis/agents/client-estimator.json`,
provisioned during workspace bootstrap (the same place the existing
`jarvis-self` is created). Schema matches the existing one
(see [specialist_service.py:111-118](../../backend/services/specialist_service.py#L111-L118)
for the field whitelist):

```json
{
  "id": "client-estimator",
  "name": "Client Estimator",
  "icon": "📋",
  "role": "Turns client RFPs and discovery materials into a structured estimate brief.",
  "system_prompt": "<see below>",
  "sources": [],
  "tools": ["search_notes", "open_note", "query_graph", "write_note"],
  "rules": [
    "Always cite the section path you draw from in [[wiki-link]] form.",
    "If a section of the brief has no source material, write 'NOT IN SOURCES' — never invent.",
    "Use Polish if the source materials are predominantly Polish."
  ],
  "examples": []
}
```

### System prompt skeleton

```
You are Client Estimator. Your job is to read the user's client documents
in workspace memory and produce one Markdown brief with these sections,
in this order:

  # {ClientName} — Estimate Brief

  ## Executive Summary           (3-5 sentences, business-level)
  ## Business Goal               (from section_type=business_goals)
  ## Functional Scope            (from section_type=requirements)
  ## Technical Scope             (from section_type=technical_constraints)
  ## Integrations                (from section_type=integrations)
  ## Risks                       (from section_type=risks)
  ## Assumptions                 (explicit; mark each "(Assumption)")
  ## Open Questions              (from section_type=open_questions
                                  + anything you cannot answer)
  ## Suggested MVP               (your synthesis — 5 bullet items max)
  ## Estimate Buckets            (S / M / L / XL per work area;
                                  no day estimates unless source says so)
  ## Recommended Next Step       (one paragraph)

For each section: cite source paths in [[wiki-link]] form. If no
source covers a topic, write "NOT IN SOURCES" — do NOT fabricate.
Final output must be saved via write_note to memory/plans/<slug>.md.
```

### Tool prefiltering by section type

When `client-estimator` is the active specialist, `search_notes`
calls from this specialist's tool loop bias towards typed sections.
Implementation: in
[backend/services/tools/executor.py](../../backend/services/tools/executor.py)
add a thin pre-step that, when the active specialist is
`client-estimator` and the search query contains a typed cue word
(reusing 28d's intent parser), passes
`preferred_section_types` through to `retrieval.retrieve(...)`.

This is a **two-line change** in the executor — the heavy lifting
(boost mechanism) was added in 28d.

### Activation flow (no UI changes)

Existing UI ([SpecialistCard.vue](../../frontend/app/components/SpecialistCard.vue),
specialist sidebar in main view) already handles activation. The
new specialist appears alongside others on first run. The only UI
adjustment is the icon registration — `📋` is fine, no new asset.

### Output format

The brief is a real Markdown note saved to
`memory/plans/{client-slug}-estimate.md` via `write_note`. That makes
it:

- Visible in Memory (singleton row, not a document tree — has no
  sections of its own).
- Indexed for retrieval (so a later question *"what did we estimate
  for ClientX?"* surfaces the brief itself).
- A node in the graph with edges to every cited source section
  through wiki-link resolution
  ([builder.py `_resolve_bidirectional_links`](../../backend/services/graph_service)).
  The estimate becomes a **bridge** between source documents in the
  graph — exactly the cross-document structure Step 27 was designed
  for.

### Eval coverage

Add 3 queries to 28c's reference set under a new `client_estimate`
type bucket *after* 28d ships:

- "summarize the OWASP-LLM Top-10 risks in three bullets"
- "what are the open questions in the HAI AI Index?"
- "what integrations does the NIST RMF require?"

Each expects retrieval to hit the typed sections. Specialist output
is not unit-tested for content (it's a Claude generation) but the
*input* it receives is — that's what determines quality, and that's
testable.

---

## Code changes

| File | Change |
|------|--------|
| [backend/services/workspace_service.py](../../backend/services/workspace_service.py) | On bootstrap, write `agents/client-estimator.json` if missing. Idempotent. |
| `backend/services/specialists/client_estimator.json` (new, asset) | The JSON template, copied at bootstrap time. |
| [backend/services/tools/executor.py](../../backend/services/tools/executor.py) | When active specialist = `client-estimator`, derive `preferred_section_types` from query and pass to `retrieval.retrieve`. |
| [backend/tests/eval/queries_reference.py](../../backend/tests/eval/queries_reference.py) | +3 queries under `client_estimate` bucket. |

No frontend changes. No new endpoints. No schema changes.

---

## Tests

- `backend/tests/test_client_estimator_bootstrap.py`:
  1. Fresh workspace ⇒ `agents/client-estimator.json` written.
  2. Pre-existing workspace with the file ⇒ not overwritten.
  3. Pre-existing workspace where the user *deleted* the file ⇒ not
     re-created (respect user intent — track via a flag in
     `app/config.json`).
- `backend/tests/test_executor_section_type_passthrough.py`:
  1. Active specialist = `client-estimator` + risk-cue query ⇒
     `preferred_section_types=["risks"]` reaches `retrieve`.
  2. Active specialist = anything else ⇒ no passthrough (default
     behaviour preserved).
- **Manual smoke** (documented, not automated): activate
  Client Estimator after re-ingesting the four reference PDFs, ask
  *"prepare an estimate brief for the OWASP/NIST package"*, verify
  the produced note (a) has all 11 headings, (b) cites at least 5
  distinct source sections, (c) marks at least one "NOT IN SOURCES".

---

## Acceptance

- A fresh workspace exposes Client Estimator in the specialist list
  on first run.
- Activating it and asking for a brief produces a Markdown note in
  `memory/plans/` whose body matches the 11-heading skeleton, with
  wiki-link citations resolving to existing section notes.
- Without 28d's section types (i.e. running this specialist on a
  workspace where sections are unclassified), the prefilter is a
  no-op and the specialist falls back to plain BM25/embedding
  retrieval — no crash, no error.
- Eval queries in the new `client_estimate` bucket score Recall@5
  ≥ 0.6 against the four reference PDFs.

---

## Out of scope

- Day-level effort estimation. Estimate Buckets are S/M/L/XL only —
  Jarvis does not invent person-days from text.
- Multiple estimate variants per client (one brief per run; user can
  re-run).
- Specialist marketplace, sharing, export.
- Auto-routing — user activates the specialist manually, matching
  the MVP usage model in the project plan.
- A custom system prompt editor for `client-estimator` from the UI
  (existing specialist editor already supports this — no special
  case needed).
