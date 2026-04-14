---
title: Hybrid Retrieval Pipeline
status: active
type: feature
sources:
  - backend/services/retrieval.py
  - backend/services/context_builder.py
depends_on: [memory, knowledge-graph]
last_reviewed: 2026-04-15
last_updated: 2026-04-15
---

# Hybrid Retrieval Pipeline

## Summary

The retrieval pipeline finds the notes most relevant to a user's message and assembles them into a compact context string for Claude. It combines full-text search with graph-aware scoring — using edge weights, entity anchors, shortest-path distance, and cluster deduplication — so that notes connected to the most relevant hits are surfaced even when they don't match the query directly.

## How It Works

The pipeline runs in two stages: retrieval (`retrieval.py`) followed by context assembly (`context_builder.py`).

**Stage 1 — retrieve()**

1. **FTS search via SQLite.** The query is passed to `memory_service.list_notes()` with a `limit` of `3×` the requested result count to provide a wide candidate pool for scoring.
2. **Load graph for scoring.** The knowledge graph is loaded from cache or disk. If no graph exists, raw FTS order is used.
3. **Extract query entities.** `_extract_query_entities()` matches query tokens against known graph node labels (persons, tags, areas). If entities are found, path scoring is enabled.
4. **Score each candidate.** For each FTS result, three scores are computed:
   - **FTS rank** — reciprocal of FTS position: `1 / (i + 1)`.
   - **Graph score** — sum of edge weights connecting this note to other FTS hits in the graph, plus a +0.3 convergence bonus if the note connects to 3+ FTS hits.
   - **Path score** (when anchors exist) — `_score_by_path()` computes the shortest weighted path (BFS, max depth 3) from the candidate to each anchor entity node. Cost = `1 / (weight + 0.01)`, so high-weight edges are cheap to traverse.
5. **Combine scores.** Without anchors: `fts_rank × 0.6 + graph_score × 0.4`. With anchors: `fts_rank × 0.4 + graph_score × 0.3 + path_score × 0.3`.
6. **Sort by final score** descending.
7. **Cluster dedup.** No more than 2 notes from the same folder are returned, preventing one folder from dominating results.
8. **Trim to limit** (default 5) and strip internal scoring fields.

**Stage 2 — build_context()**

1. **User preferences.** `preference_service.format_for_prompt()` is called first. If preferences are set, they appear at the top of the context so Claude sees behavioral constraints before any note content.
2. **Specialist knowledge injection.** If a specialist is active, its knowledge files (`.md`, `.txt`, `.csv`, `.json`, `.pdf`) in `agents/{id}/` are checked for relevance against the user's message using keyword overlap. Only files with at least one matching keyword are injected, ranked by overlap count (most relevant first). Each file is truncated at 1,500 characters; the total specialist knowledge budget is 4,000 characters. Stop words and short tokens are excluded from matching. If the message has no extractable keywords, no files are injected.
3. **Retrieve.** Calls `retrieve()` with `limit=5`.
4. **Specialist scoping.** If a specialist is active and declares `sources`, results are filtered to only notes whose paths fall within those source folders. This keeps specialists from leaking out-of-scope knowledge into each other's answers.
5. **Note content fetching.** The top 3 results are read from disk. Each note's content is hard-truncated at 500 characters and wrapped in `<retrieved_note>` XML tags to prevent prompt injection. Failures are silently skipped so a missing note never blocks a response.
6. **Assembly.** Note blocks are joined with `\n---\n` separators, then combined with the preferences and specialist knowledge blocks using `\n\n`. If nothing was found, `None` is returned.
7. **Token estimate.** Returns a tuple `(context_text, token_estimate)` where `token_estimate = len(text) // 4`.

The 500-character truncation, 3-note cap, and 4,000-character specialist knowledge budget are the primary token-budget controls.

### Graph-scoped context

`build_graph_scoped_context(node_id, user_message)` builds context from a node's graph neighborhood only, without FTS search. It fetches depth-2 neighbors, reads up to 5 note neighbors (500 chars each), and wraps them in `<retrieved_note>` tags. This is used when the user navigates to chat from the graph's node detail panel ("Ask about this").

## Key Files

- `backend/services/retrieval.py` — Weighted hybrid FTS + graph scoring, entity-based path scoring, BFS shortest weighted path, cluster dedup.
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

Returns a ranked list of note dicts. Each dict contains at minimum a `"path"` key and a `"folder"` key. Scoring is graph-weighted when graph data is available, with cluster dedup limiting folder repetition.

Returns an empty list if `query` is blank or whitespace-only.

### `build_context()`

```python
async def build_context(
    user_message: str,
    workspace_path=None,
) -> Tuple[Optional[str], int]:
```

Returns a tuple of `(context_text, token_estimate)`. `context_text` is a ready-to-inject context string or `None` if no relevant notes or preferences were found. `token_estimate` is `len(text) // 4` or `0`. The string combines user preferences, specialist knowledge, and up to 3 truncated note bodies. This return value is used directly by the chat service when constructing the system prompt sent to Claude.

### `build_graph_scoped_context()`

```python
async def build_graph_scoped_context(
    node_id: str,
    user_message: str,
    workspace_path=None,
) -> Optional[str]:
```

Returns a context string scoped to the node's neighborhood (depth 2, max 5 notes), or `None` if no neighbor notes were found.

## Gotchas

- **Graph scoring requires a built graph.** If no `graph.json` exists, `retrieve()` falls back to raw FTS order with no graph weighting. The first run after workspace creation will behave purely as keyword search until the graph is built.
- **Entity anchor matching is substring-based.** `_extract_query_entities()` checks if a node label appears anywhere in the query (lowercased). This can produce false positives for short labels like "AI" or "Go".
- **BFS shortest-path is approximate.** `_shortest_weighted_path()` uses layered BFS (not Dijkstra), so it doesn't guarantee the true shortest weighted path — it finds the minimum-cost step at each layer. For max depth 3 this is generally close enough.
- **Silent note-read failures.** If a note's path exists in the index but the file is missing on disk, `build_context()` skips it without logging. A partially deleted workspace can silently reduce context quality.
- **Specialist scoping strips graph-scored notes too.** `_scope_results()` filters by path prefix without distinguishing FTS from graph results. A graph-scored note that lives outside a specialist's declared sources will be dropped even if it's highly relevant.
- **500-character truncation is unconditional.** Long notes are always cut at 500 characters regardless of how short the rest of the context is. There is no fill-up logic that uses the remaining token budget.
- **Cluster dedup cap of 2 per folder.** In workspaces where most notes live in one folder (e.g. `inbox/`), the cap aggressively limits results — potentially returning fewer than `limit` items.
- **`workspace_path` threading.** Both functions accept a `workspace_path` argument that is forwarded to all service calls. Passing `None` in both calls is safe — each underlying service falls back to its own default — but passing mismatched values between `retrieve()` and `build_context()` would silently produce results from different workspaces.
