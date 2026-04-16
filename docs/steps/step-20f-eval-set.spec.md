# Step 20f — Evaluation Benchmark

> **Goal**: Create an evaluation harness with 50+ queries and expected results
> so we can measure whether each semantic upgrade actually improves retrieval.
> Run this FIRST to establish baseline, then re-run after each step.

**Status**: ⬜ Not started
**Depends on**: Nothing (uses existing retrieval pipeline)
**Effort**: ~1 day
**Run order**: FIRST (before 20a)

---

## Why This Matters

Without a benchmark, "semantic improvements" are feelings, not facts.
We need to know:
- Does chunking actually improve recall?
- Do semantic anchors find better graph connections than substring?
- Does entity canonicalization reduce duplicate nodes?

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Test corpus | 20 synthetic notes covering overlapping topics, people, projects |
| Query set | 50 queries: keyword, semantic, relational, temporal |
| Expected results | For each query: list of relevant note paths + relevant graph nodes |
| Eval runner | Script that runs queries against current pipeline and scores them |
| Metrics | Recall@K, MRR, Precision@K, graph anchor accuracy |
| Baseline snapshot | Results saved as JSON for comparison after each step |

---

## File Structure

```
backend/
  tests/
    eval/
      __init__.py
      corpus.py              # NEW — synthetic notes for eval
      queries.py             # NEW — 50 queries with expected results
      runner.py              # NEW — run queries, compute metrics
      test_eval_baseline.py  # NEW — pytest wrapper
  eval_results/              # gitignored — baseline + per-step snapshots
```

---

## Implementation Details

### 1. Test Corpus (`corpus.py`)

Create 20 notes that cover:
- **Overlapping topics**: sleep, productivity, health, travel, projects
- **People**: at least 5 named people with aliases (e.g., "Michał Kowalski" / "Michał")
- **Cross-references**: wiki-links between notes, shared tags
- **Varying length**: short notes (1 paragraph) and long notes (5+ sections)
- **Languages**: primarily English, 2-3 notes in Polish (Jarvis is multilingual)

```python
EVAL_CORPUS = [
    {
        "path": "projects/website-redesign.md",
        "content": """---
title: Website Redesign Project
tags: [project, web, design]
people: [Michał Kowalski, Anna]
created_at: 2026-03-01
---

## Goals
Redesign the company website by Q2...

## Meeting Notes
Met with Michał about the new landing page...
Anna suggested using a card-based layout...

## Technical Decisions
- Framework: Nuxt 3
- Hosting: Vercel
- CMS: Markdown files

Related: [[travel/conference-notes.md]]
""",
    },
    # ... 19 more notes
]
```

### 2. Query Set (`queries.py`)

Each query has:
- `query`: the search string
- `type`: keyword | semantic | relational | temporal
- `expected_paths`: notes that SHOULD appear in top-5
- `expected_anchors`: graph nodes that SHOULD be matched as anchors
- `notes`: explanation of why these are expected

```python
EVAL_QUERIES = [
    {
        "query": "what did Michał say about the website",
        "type": "relational",
        "expected_paths": ["projects/website-redesign.md"],
        "expected_anchors": ["person:Michał Kowalski"],
        "notes": "Should find via person mention + project topic",
    },
    {
        "query": "how to improve my sleep quality",
        "type": "semantic",
        "expected_paths": ["health/sleep-tracking.md", "health/evening-routine.md"],
        "expected_anchors": ["tag:health", "tag:sleep"],
        "notes": "Semantic match — 'evening routine' doesn't mention 'sleep quality' literally",
    },
    # ... 48 more queries
]
```

### 3. Eval Runner (`runner.py`)

```python
async def run_eval(
    workspace_path: Path,
    queries: list[dict],
    limit: int = 5,
) -> dict:
    """Run all queries against current retrieval pipeline."""
    results = []
    for q in queries:
        retrieved = await retrieval.retrieve(
            q["query"], limit=limit, workspace_path=workspace_path,
        )
        retrieved_paths = [r["path"] for r in retrieved]

        # Compute metrics per query
        expected = set(q["expected_paths"])
        found = set(retrieved_paths) & expected
        recall = len(found) / len(expected) if expected else 1.0

        # MRR: rank of first expected result
        mrr = 0.0
        for i, path in enumerate(retrieved_paths):
            if path in expected:
                mrr = 1.0 / (i + 1)
                break

        results.append({
            "query": q["query"],
            "type": q["type"],
            "recall": recall,
            "mrr": mrr,
            "expected": list(expected),
            "retrieved": retrieved_paths,
            "signals": [r.get("_signals", {}) for r in retrieved],
        })

    # Aggregate metrics
    avg_recall = sum(r["recall"] for r in results) / len(results)
    avg_mrr = sum(r["mrr"] for r in results) / len(results)

    by_type = {}
    for r in results:
        t = r["type"]
        by_type.setdefault(t, []).append(r)

    type_metrics = {
        t: {
            "avg_recall": sum(r["recall"] for r in rs) / len(rs),
            "avg_mrr": sum(r["mrr"] for r in rs) / len(rs),
            "count": len(rs),
        }
        for t, rs in by_type.items()
    }

    return {
        "overall": {"avg_recall": avg_recall, "avg_mrr": avg_mrr, "total": len(results)},
        "by_type": type_metrics,
        "details": results,
    }
```

### 4. Graph Anchor Eval (bonus)

Also measure graph anchor quality:

```python
async def eval_graph_anchors(
    queries: list[dict],
    workspace_path: Path,
) -> dict:
    """Measure how well _extract_query_entities matches expected anchors."""
    graph = graph_service.load_graph(workspace_path)
    if not graph:
        return {"error": "no graph"}

    hits = 0
    total = 0
    for q in queries:
        if not q.get("expected_anchors"):
            continue
        actual = retrieval._extract_query_entities(q["query"], graph)
        expected = set(q["expected_anchors"])
        total += len(expected)
        hits += len(set(actual) & expected)

    return {"anchor_recall": hits / total if total else 0, "total_expected": total}
```

### 5. Baseline Snapshot

After running eval on current codebase (pre-chunking):

```json
{
  "step": "baseline",
  "timestamp": "2026-04-16T...",
  "overall": {"avg_recall": 0.42, "avg_mrr": 0.35, "total": 50},
  "by_type": {
    "keyword": {"avg_recall": 0.72, "avg_mrr": 0.65, "count": 15},
    "semantic": {"avg_recall": 0.28, "avg_mrr": 0.20, "count": 15},
    "relational": {"avg_recall": 0.35, "avg_mrr": 0.30, "count": 10},
    "temporal": {"avg_recall": 0.30, "avg_mrr": 0.25, "count": 10}
  },
  "anchor_recall": 0.40
}
```

These numbers are hypothetical — real baseline will show where the pipeline is weakest.

---

## Test Cases

```python
# test_eval_baseline.py

async def test_eval_corpus_loads():
    """All 20 corpus notes create successfully."""

async def test_eval_runner_produces_metrics():
    """Runner returns overall + by_type + details."""

async def test_baseline_recall_above_zero():
    """Current pipeline has non-zero recall (sanity check)."""

async def test_keyword_queries_outperform_semantic():
    """Baseline: keyword queries have higher recall than semantic
    (expected — current pipeline is BM25-first)."""
```

---

## Acceptance Criteria

- [ ] 20 synthetic notes in `corpus.py` covering diverse topics/people/links
- [ ] 50 queries in `queries.py` with expected results and types
- [ ] `runner.py` computes Recall@5, MRR, per-type breakdown
- [ ] Graph anchor eval measures anchor recall
- [ ] Baseline snapshot saved to `eval_results/baseline.json`
- [ ] Pytest wrapper runs full eval in <30s (uses fake embeddings)
- [ ] Baseline numbers documented — this is the bar to beat
