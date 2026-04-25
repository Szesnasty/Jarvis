# Step 28c — Eval Baseline Against Reference PDFs

> **Goal**: Freeze a reproducible retrieval baseline against the four
> reference PDFs from Step 27. Every change after this step (28d
> classification, 28e specialist, future weight tuning) must be
> measured against the same numbers, not eyeballed.

**Parent**: [step-28-document-intelligence.md](step-28-document-intelligence.md)
**Status**: ⬜ Planned

---

## Why

A harness already exists at
[backend/tests/eval/runner.py](../../backend/tests/eval/runner.py) and
computes Recall, MRR, Precision@K
([runner.py:34-46](../../backend/tests/eval/runner.py#L34-L46)). What
is missing:

- The corpus is synthetic
  ([corpus.py](../../backend/tests/eval/corpus.py)) — three short
  hand-written notes about Portugal, supplements, and a website
  redesign. Nothing resembling a 100-page PDF, no section-split
  notes, no graph density.
- The query set
  ([queries.py](../../backend/tests/eval/queries.py)) was written for
  that synthetic corpus.
- There is no checked-in baseline JSON. Runs are not comparable
  across commits.

Without those three additions, a delta from 28d ("classified
sections improve retrieval by 12%") is not falsifiable.

---

## Design

### Reference corpus

Use the same four PDFs Step 27 was specified against:

- HAI AI Index Report 2025
- OWASP LLM Top-10
- NIST AI Risk Management Framework
- A Survey of Large Language Models

**Do not check the PDFs into the repo.** Instead, check in:

- `backend/tests/eval/fixtures/reference_pdfs.json` — manifest of
  expected file SHA-256 + URL where the user can fetch them.
- `backend/tests/eval/fixtures/reference_workspace/` — a
  pre-ingested, hand-curated workspace snapshot **with the section
  Markdown files only** (no original PDFs). These are deterministic
  outputs of `_emit_pdf_sections` after Step 27, ~1–2 MB total.

A small bootstrap script `backend/tests/eval/setup_reference.py`
verifies SHAs (skips if user hasn't downloaded the source PDFs;
skips evaluation entirely with a clear message rather than
half-running).

### Query set

`backend/tests/eval/queries_reference.py` — separate from the
existing synthetic queries. Target: **30 queries** distributed:

| Bucket | Count | Example |
|--------|-------|---------|
| Direct factual | 8 | "what does the OWASP top 10 say about prompt injection?" |
| Cross-document | 6 | "how do NIST RMF and OWASP overlap on data poisoning?" |
| Section-typed (for 28d) | 8 | "what risks are listed for LLM deployments?" |
| Polish | 4 | "co OWASP mówi o prompt injection?" |
| Numerical / specific | 4 | "what was the AI training compute growth in 2024 per HAI?" |

Each query carries:

```python
{
  "query": "...",
  "type": "factual" | "cross_doc" | "section_typed" | "polish" | "numerical",
  "expected_paths": ["knowledge/owasp-llm-top-10/03-prompt-injection.md", ...],
  "expected_section_types": ["risks"],   # for type=section_typed; ignored otherwise
  "min_recall": 0.5,                      # per-query floor (CI gate)
  "notes": "..."
}
```

The `min_recall` field lets us mark some queries as harder than
others without dragging the average down to 0.

### Runner extensions

Extend `runner.py` with:

1. Per-query budget reporting: token count of the assembled prompt.
   Pull from `context_builder` — it already trims to a token budget
   so the cost is computed.
2. Aggregate by `type`: separate Recall@5 / MRR for `factual` vs
   `cross_doc` vs `section_typed`. A single average hides where
   regressions land.
3. JSON output with stable key order, suitable for `git diff`:
   `backend/tests/eval/baselines/step-28c.json`.

### Baseline freeze

Run the harness once, manually, on a clean re-ingest of the four
PDFs. Commit the resulting JSON as the baseline. Add a pytest:

```python
# backend/tests/eval/test_baseline_floor.py
def test_eval_no_regression():
    baseline = json.loads(BASELINE_PATH.read_text())
    current = run_eval_sync(...)
    for q_name, prev in baseline["per_query"].items():
        cur = current["per_query"][q_name]
        assert cur["recall"] >= prev["recall"] - 0.05, (
            f"{q_name}: recall {cur['recall']:.2f} vs baseline {prev['recall']:.2f}"
        )
```

5% tolerance per query, no tolerance on mean Recall@5.

This pytest is **opt-in** behind an env var
(`JARVIS_EVAL_FLOOR=1`) so CI doesn't fail when the reference
workspace is absent. It's a pre-merge check, not a unit test.

### CLI script

`backend/scripts/run_eval.py`:

```bash
python backend/scripts/run_eval.py \
  --workspace ~/Jarvis-eval \
  --baseline backend/tests/eval/baselines/step-28c.json \
  --output ./eval-run.json
```

Prints a diff table:

```
Query                                       Recall   Δ        MRR     Δ
"what does OWASP say about prompt inj…"     0.83     +0.00    1.00    +0.00
"co OWASP mówi o prompt injection?"         0.50     -0.17 ⚠   0.33    -0.33 ⚠
…
mean (factual)                              0.78     +0.02
mean (cross_doc)                            0.61     -0.05 ⚠
```

---

## Code changes

| File | Change |
|------|--------|
| `backend/tests/eval/queries_reference.py` (new) | 30 reference queries. |
| `backend/tests/eval/fixtures/reference_pdfs.json` (new) | SHA + URL manifest. |
| `backend/tests/eval/fixtures/reference_workspace/…` (new) | Pre-ingested section Markdowns + `jarvis.db` snapshot. ~1–2 MB. |
| `backend/tests/eval/setup_reference.py` (new) | Verifies fixtures, skips cleanly if missing. |
| [backend/tests/eval/runner.py](../../backend/tests/eval/runner.py) | Per-bucket aggregation, token-budget field. |
| `backend/tests/eval/baselines/step-28c.json` (new, committed) | Baseline numbers. |
| `backend/tests/eval/test_baseline_floor.py` (new) | Per-query no-regression gate behind `JARVIS_EVAL_FLOOR=1`. |
| `backend/scripts/run_eval.py` (new) | CLI diff runner. |

No application code changes. This step only adds tooling and data.

---

## Tests

The eval harness *is* the test. Plus:

- `backend/tests/eval/test_runner_aggregation.py`:
  1. Synthetic results aggregate correctly per bucket.
  2. Empty bucket (no queries of that type) does not crash.
  3. Baseline diff produces stable key order.

---

## Acceptance

- Running `python backend/scripts/run_eval.py --workspace …` against
  a freshly re-ingested reference workspace prints all 30 queries,
  their per-bucket means, and writes a JSON.
- `backend/tests/eval/baselines/step-28c.json` exists in git after
  this step lands.
- `JARVIS_EVAL_FLOOR=1 pytest backend/tests/eval/test_baseline_floor.py`
  passes immediately after the baseline is recorded.
- Mean Recall@5 across all 30 queries ≥ 0.55 (this is the floor that
  Step 28d/28e must improve, not regress).

---

## Out of scope

- Hosting reference PDFs ourselves. Manifest only.
- Continuous eval in CI. The harness needs human-curated PDFs and
  a clean ingest — not a CI-friendly setup. Pre-merge local check
  only.
- Cross-language evaluation beyond the 4 PL queries.
- Hyperparameter sweep over fusion weights (separate future step).
