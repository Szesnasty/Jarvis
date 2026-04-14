---
title: Hybrid Retrieval Pipeline
status: active
type: feature
sources:
  - backend/services/retrieval.py
  - backend/services/context_builder.py
depends_on: [memory, knowledge-graph]
last_reviewed: 2026-04-14
---

# Hybrid Retrieval Pipeline

## Summary

The retrieval pipeline finds the notes most relevant to a user's message and assembles them into a compact context string for Claude. It combines full-text search results with graph-based neighbor expansion so that notes connected to the most relevant hits are surfaced even when they don't match the query directly.

## How It Works

The pipeline runs in two stages: retrieval (`retrieval.py`) followed by context assembly (`context_builder.py`).

**Stage 1 — retrieve()**

1. **FTS search via SQLite.** The query is passed to `memory_service.list_notes()` with a `limit` of `2×` the requested result count to leave headroom for later deduplication.
2. **Graph expansion.** For each of the top 3 FTS hits, the graph service fetches depth-1 neighbors. Only nodes typed as `"note"` (IDs prefixed `note:`) are considered. This surfaces notes that are connected in the knowledge graph but may not contain the query keywords themselves.
3. **Merge and deduplicate.** Graph-expanded results are appended only if their path wasn't already returned by FTS.
4. **Ranking.** FTS matches sort before graph expansions. The final list is trimmed to the requested `limit` (default 5).

**Stage 2 — build_context()**

1. **User preferences.** `preference_service.format_for_prompt()` is called first. If preferences are set, they appear at the top of the context so Claude sees behavioral constraints before any note content.
2. **Retrieve.** Calls `retrieve()` with `limit=5`.
3. **Specialist scoping.** If a specialist is active and declares `sources`, results are filtered to only notes whose paths fall within those source folders. This keeps specialists from leaking out-of-scope knowledge into each other's answers.
4. **Note content fetching.** The top 3 results are read from disk. Each note's content is hard-truncated at 500 characters. Failures are silently skipped so a missing note never blocks a response.
5. **Assembly.** Note blocks are joined with `\n---\n` separators, then combined with the preferences block using `\n\n`. If nothing was found, `None` is returned and the caller proceeds without injected context.

The 500-character truncation and 3-note cap are the primary token-budget controls. There is no dynamic sizing — the budget is fixed at roughly 1,500 characters of note content per call.

## Key Files

- `backend/services/retrieval.py` — FTS search, graph neighbor expansion, merge, and rank.
- `backend/services/context_builder.py` — Orchestrates retrieval, applies specialist scoping, fetches note bodies, and produces the final context string for Claude.

## API / Interface

### `retrieve()`

```python
async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> List[Dict]:
```

Returns a ranked list of note dicts. Each dict contains at minimum a `"path"` key. Graph-expanded entries also carry `"source": "graph"` and a `"label"` key from the graph node. FTS results carry whatever fields `memory_service.list_notes()` returns.

Returns an empty list if `query` is blank or whitespace-only.

### `build_context()`

```python
async def build_context(
    user_message: str,
    workspace_path=None,
) -> Optional[str]:
```

Returns a ready-to-inject context string, or `None` if no relevant notes or preferences were found. The string combines user preferences and up to 3 truncated note bodies. This return value is used directly by the chat service when constructing the system prompt sent to Claude.

## Gotchas

- **Graph expansion only covers the top 3 FTS results.** Notes ranked 4th or lower in the FTS pass never seed graph expansion, regardless of `limit`. If the most relevant note ranks low in FTS, its graph neighbors won't be discovered.
- **Silent note-read failures.** If a note's path exists in the index but the file is missing on disk, `build_context()` skips it without logging. A partially deleted workspace can silently reduce context quality.
- **Specialist scoping strips graph-expanded notes too.** `_scope_results()` filters by path prefix without distinguishing FTS from graph results. A graph-expanded note that lives outside a specialist's declared sources will be dropped even if it's highly relevant.
- **500-character truncation is unconditional.** Long notes are always cut at 500 characters regardless of how short the rest of the context is. There is no fill-up logic that uses the remaining token budget.
- **`workspace_path` threading.** Both functions accept a `workspace_path` argument that is forwarded to all service calls. Passing `None` in both calls is safe — each underlying service falls back to its own default — but passing mismatched values between `retrieve()` and `build_context()` would silently produce results from different workspaces.

## Known Issues

**Critical — Prompt injection via unsanitized note content (`context_builder.py:52-53`).**
Note content is embedded verbatim into the system prompt with no sanitization, escaping, or structural delimiting beyond a bracketed path prefix. A note whose content contains instruction-like text (especially notes ingested from external URLs) could influence Claude's behavior or override intended constraints. Until a sanitization or clear-delimiting strategy is in place, URL-ingested content carries elevated risk.

**Medium — Hard 500-character truncation breaks mid-word (`context_builder.py:52`).**
`note["content"][:500]` cuts at a byte position with no awareness of word or sentence boundaries. The resulting fragment sent to Claude may end mid-word or mid-sentence, which can degrade comprehension quality for notes whose key information falls near the boundary. A word-boundary or sentence-boundary truncation would improve this at negligible cost.

**Medium — Token budgets are never enforced during context building.**
A `token_tracking` module exists and records usage after the fact, but `build_context` applies no dynamic token budget during assembly. The fixed 500-character × 3-note cap is the only constraint. If token budgets are ever made configurable (e.g., per specialist), `build_context` would need to read and apply them rather than relying solely on the static truncation limit.
