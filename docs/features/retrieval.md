---
title: Hybrid Retrieval Pipeline
status: active
type: feature
sources:
  - backend/services/retrieval/__init__.py
  - backend/services/retrieval/pipeline.py
  - backend/services/context_builder.py
depends_on: [memory, knowledge-graph]
last_reviewed: 2026-04-25
last_updated: 2026-04-25
---

# Hybrid Retrieval Pipeline

## Summary

The retrieval pipeline finds the notes most relevant to a user's message and assembles them into a compact context string for Claude. It fuses three independent signals — **BM25** full-text ranking, **cosine similarity** over local embeddings, and **graph** connectivity scoring — into a single ranked list. Each signal contributes a normalized `[0, 1]` score with default weights `0.25 / 0.40 / 0.35`, and weights are renormalized on the fly when a signal is unavailable so the pipeline degrades gracefully (no embeddings, no graph, or neither). Every returned note carries a `_signals` dict exposing the raw per-signal scores for transparency and debugging.

> **Note**: As of step 22f, `retrieval.py` was refactored into a `retrieval/` package. The core pipeline logic lives in `retrieval/pipeline.py`; imports via `from services.retrieval import retrieve` remain unchanged. See [jira-retrieval.md](jira-retrieval.md) for the Jira-aware extensions.

## How It Works

The pipeline runs in two stages: retrieval (`retrieval.py`) followed by context assembly (`context_builder.py`).

**Stage 1 — retrieve()**

1. **Signal 1 — BM25 candidates.** `memory_service.list_notes(search=query, limit=limit*3)` runs the FTS5 query. Each candidate carries a `_bm25_score` from SQLite's built-in BM25 ranker. Scores are normalized against the maximum absolute score in the candidate pool to produce a `[0, 1]` value per note. This is the seed candidate pool.
2. **Signal 2 — cosine similarity.** If `JARVIS_DISABLE_EMBEDDINGS` is not set and `embedding_service.is_available()` returns true, `search_similar(query, limit*3)` runs the query through the local fastembed model and scores every embedded note by cosine similarity. Scores are clamped to `[0, 1]` (cosine can be negative). Notes already in the candidate pool get their `_cosine` field updated; notes found only by embeddings (no BM25 match) are looked up via `_get_note_meta()` directly from SQLite and joined into the pool with `_bm25 = 0`. Cosine failure (`ImportError`, model load error) is logged as a warning and the pipeline continues without this signal.
3. **Signal 3 — graph scoring.** The knowledge graph is loaded from cache or disk. When present, `_extract_query_entities()` matches query tokens against known graph node labels (persons, tags, areas). `_compute_graph_score()` then computes, for each candidate, the sum of:
   - **Edge connectivity** — weighted edges linking the note to other candidates in the pool.
   - **Convergence bonus** — `+0.3` if the note connects to 3+ other candidates.
   - **Path score** — when query entities matched anchors, `_score_by_path()` computes the shortest weighted BFS path (max depth 3) from the candidate to each anchor. Step cost is `1 / (edge.weight + 0.01)` so high-weight edges are cheap to traverse.
   - **Cluster bonus** — `min(similar_to_neighbors × 0.15, 0.45)`, boosting notes that share semantic similarity edges with other candidates.

   The raw graph score is capped at `1.0`.
4. **Weighted fusion.** Weights default to `WEIGHT_BM25 = 0.35`, `WEIGHT_COSINE = 0.35`, `WEIGHT_GRAPH = 0.30`. Any missing signal is zeroed and the remaining weights are renormalized so they still sum to `1.0`. The final score per note is `w_bm25*bm25 + w_cos*cosine + w_graph*graph`.
5. **Sort** by `(score, updated_at)` descending — recency is the tiebreaker when scores are equal.
6. **Cluster dedup.** `_cluster_dedup()` enforces at most 2 notes per folder so a single folder can't dominate the output, then trims to `limit`.
7. **Cleanup.** Internal scoring fields (`_score`, `_bm25`, `_cosine`, `_graph`, `_bm25_score`, `_node_id`) are stripped from the returned dicts. The `_signals` dict is preserved for transparency — callers can inspect which signal drove each result.

**Stage 2 — build_context()**

1. **User preferences.** `preference_service.format_for_prompt()` is called first. If preferences are set, they appear at the top of the context so Claude sees behavioral constraints before any note content.
2. **Specialist knowledge injection.** If a specialist is active, its knowledge files (`.md`, `.txt`, `.csv`, `.json`, `.pdf`) in `agents/{id}/` are checked for relevance against the user's message using keyword overlap. Only files with at least one matching keyword are injected, ranked by overlap count (most relevant first). Each file is truncated at 1,500 characters; the total specialist knowledge budget is 4,000 characters. Stop words and short tokens are excluded from matching. If the message has no extractable keywords, no files are injected.
3. **Retrieve.** Calls `retrieve()` with `limit=5`.
4. **Specialist scoping.** If a specialist is active and declares `sources`, results are filtered to only notes whose paths fall within those source folders. This keeps specialists from leaking out-of-scope knowledge into each other's answers.
5. **Note content fetching.** The top 3 results are read from disk. Each note's content is hard-truncated at 500 characters and wrapped in `<retrieved_note>` XML tags to prevent prompt injection. Failures are silently skipped so a missing note never blocks a response.
6. **Assembly.** Note blocks are joined with `\n---\n` separators, then combined with the preferences and specialist knowledge blocks using `\n\n`. If nothing was found, `None` is returned.
7. **Token estimate.** Returns a tuple `(context_text, token_estimate)` where `token_estimate = len(text) // 4`.

The 500-character truncation, 3-note cap, and 4,000-character specialist knowledge budget are the primary token-budget controls.

### Graceful degradation

The pipeline is designed to work with 1, 2, or 3 active signals:

| BM25 | Cosine | Graph | Behaviour                                             |
|------|--------|-------|-------------------------------------------------------|
| ✅   | ✅     | ✅    | Full fusion at `0.35 / 0.35 / 0.30`.                   |
| ✅   | ✅     | ❌    | No graph — weights renormalize to `0.5 / 0.5`.         |
| ✅   | ❌     | ✅    | fastembed not installed — renormalize to `0.54 / 0.46`.|
| ✅   | ❌     | ❌    | Pure BM25 with folder dedup.                           |

Cosine is disabled when `JARVIS_DISABLE_EMBEDDINGS=1` (test mode), when `fastembed` is not installed, or when `search_similar` raises. Graph is disabled when no `graph.json` exists yet.

### Graph-scoped context

`build_graph_scoped_context(node_id, user_message)` builds context from a node's graph neighborhood only, without FTS search. It fetches depth-2 neighbors, reads up to 5 note neighbors (500 chars each), and wraps them in `<retrieved_note>` tags. This is used when the user navigates to chat from the graph's node detail panel ("Ask about this").

## Key Files

- `backend/services/retrieval.py` — 3-signal hybrid fusion (BM25 + cosine + graph), weight renormalization, `_compute_graph_score` (edge connectivity + convergence + path + similar_to cluster bonus), folder dedup, `_signals` transparency.
- `backend/services/context_builder.py` — Orchestrates retrieval, applies specialist scoping, fetches note bodies, produces the final `(context_text, token_estimate)` tuple for Claude. Also provides `build_graph_scoped_context()` and the shared `_extract_keywords()` utility.

## API / Interface

### `retrieve()`

```python
async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> List[Dict]:
```

Returns a ranked list of note dicts. Each dict contains at minimum a `"path"` key, a `"folder"` key, and a `"_signals"` dict of the form:

```python
{"bm25": 0.72, "cosine": 0.45, "graph": 0.31}
```

Any missing signal is reported as `0.0`. Internal intermediate fields are stripped before return.

Returns an empty list if `query` is blank or whitespace-only, or if no signal produced any candidates.

### `build_context()`

```python
async def build_context(
    user_message: str,
    workspace_path=None,
) -> Tuple[Optional[str], int, List[dict]]:
```

Returns `(context_text, token_estimate, trace)`. `context_text` is a ready-to-inject context string or `None` if no relevant notes or preferences were found. `token_estimate` is `len(text) // 4` or `0`. `trace` is the per-note retrieval trace described below — empty list when nothing was retrieved. This return value is used directly by the chat service when constructing the system prompt sent to Claude; the chat router then forwards `trace` to the WebSocket as a `trace` event.

### `build_graph_scoped_context()`

```python
async def build_graph_scoped_context(
    node_id: str,
    user_message: str,
    workspace_path=None,
) -> Tuple[Optional[str], List[dict]]:
```

Returns `(context_text, trace)` scoped to the node's neighborhood (depth 2, max 5 notes). The trace lists the focal note as a primary entry and each connected neighbour as an expansion entry.

### Retrieval trace (step 28a)

Both context builders collect a structured per-note trace alongside the prompt string. Each entry has the shape:

```python
{
  "path": "knowledge/hai-ai-index/03-research-and-development.md",
  "title": "Research and Development",
  "score": 0.74,
  "reason": "primary",                # primary | expansion
  "via": "cosine",                    # bm25 | cosine | graph | rerank | …
  "edge_type": None,                  # set when reason=expansion
  "tier": None,                       # strong | weak when via=graph
  "signals": {"bm25": 0.42, "cosine": 0.81, "graph": 0.30}
}
```

`via` is the dominant signal (the key with the highest value in `_signals`) for primary entries. Expansion entries always carry `via="graph"` plus the originating `edge_type` and `tier`. The trace covers what was actually emitted into the prompt; candidates dropped by token budget or unreadable files do not appear.

### Tuning constants

```python
WEIGHT_BM25 = 0.35
WEIGHT_COSINE = 0.35
WEIGHT_GRAPH = 0.30
```

Defined at module top of `retrieval.py`. Changing these rebalances signal influence; the renormalization logic guarantees the effective weights still sum to 1.0 even when a signal is absent.

## Gotchas

- **Cosine is disabled entirely under `JARVIS_DISABLE_EMBEDDINGS=1`.** The test suite sets this env var by default (see `conftest.py`) to avoid loading the 220MB fastembed model on every run. Tests that need the full pipeline must clear the var and stub the embedding functions to stay fast.
- **`fastembed` is an optional dependency.** If it isn't installed the pipeline silently falls back to `BM25 + graph`. The retrieval code catches `ImportError` without logging, so the only indication that cosine was unavailable is an all-zero `_cosine` signal on results.
- **Cosine scores are clamped to `[0, 1]`.** Embeddings can return slightly negative cosine values for unrelated content; those become `0` rather than pulling the final score below zero.
- **Graph scoring requires a built graph.** If no `graph.json` exists, the graph signal is zeroed and its weight is renormalized out. The first run after workspace creation will rank by `BM25 + cosine` until the graph is rebuilt.
- **Entity anchor matching is substring-based.** `_extract_query_entities()` checks if a node label appears anywhere in the lowercased query. This can produce false positives for short labels like "AI" or "Go".
- **BFS shortest-path is approximate.** `_shortest_weighted_path()` uses layered BFS (not Dijkstra), so it doesn't guarantee the true shortest weighted path — it finds the minimum-cost step at each layer. For max depth 3 this is generally close enough.
- **Cluster dedup cap of 2 per folder.** In workspaces where most notes live in one folder (e.g. `inbox/`), the cap aggressively limits results — potentially returning fewer than `limit` items.
- **Recency is only a tiebreaker.** Two notes with the same fused score are sorted by `updated_at` descending, but recency has zero influence when scores differ. A months-old note with a high BM25 + cosine match will still outrank yesterday's weakly matching note.
- **Silent note-read failures.** If a note's path exists in the index but the file is missing on disk, `build_context()` skips it without logging. A partially deleted workspace can silently reduce context quality.
- **Specialist scoping strips graph-scored notes too.** `_scope_results()` filters by path prefix without distinguishing signal sources. A graph-scored note that lives outside a specialist's declared sources will be dropped even if it's highly relevant.
- **500-character truncation is unconditional.** Long notes are always cut at 500 characters regardless of how short the rest of the context is. There is no fill-up logic that uses the remaining token budget.
- **`workspace_path` threading.** Both functions accept a `workspace_path` argument that is forwarded to all service calls. Passing `None` in both calls is safe — each underlying service falls back to its own default — but passing mismatched values between `retrieve()` and `build_context()` would silently produce results from different workspaces.
