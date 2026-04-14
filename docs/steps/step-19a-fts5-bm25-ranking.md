# Step 19a — Fix FTS5 BM25 Ranking

> **Goal**: Make full-text search actually return the best matches first.
> Currently FTS results are sorted by `updated_at`, discarding SQLite's
> built-in BM25 relevance scoring. Fix this so keyword search feels useful
> before we even add embeddings.

**Status**: ⬜ Not started
**Depends on**: Nothing (independent quick win)
**Effort**: ~2–3 hours

---

## Why This Matters

Right now a user searching "vacation plans" gets notes sorted by recency,
not relevance. A note titled "Vacation Plans 2025" updated months ago loses
to yesterday's grocery list that mentions "plans". Fixing BM25 ranking is
the single highest-value change for search quality with zero new dependencies.

---

## Problems in Current Code

| Problem | Where | Impact |
|---------|-------|--------|
| `ORDER BY n.updated_at DESC` instead of `ORDER BY rank` | `memory_service.list_notes()` | BM25 scores are computed but thrown away |
| Implicit AND (all tokens required) | `" ".join(t + "*" for t in tokens)` | "vacation plan" returns nothing if note has "vacation" but not "plan" |
| No column weighting | FTS5 table has equal weight on title, body, tags | Title match should rank higher than body mention |
| Retrieval pipeline uses positional rank | `retrieval.py` line `fts_rank = 1.0 / (i + 1)` | Depends on list ordering but list is by date not relevance |

---

## What This Step Covers

| Change | Description |
|--------|-------------|
| BM25 ordering | `ORDER BY rank` in FTS search query |
| Column weights | `bm25(notes_fts, 10.0, 1.0, 5.0)` — title 10×, body 1×, tags 5× |
| OR fallback | Try AND match first, fall back to OR if too few results |
| Return BM25 score | Include `_bm25_score` in results for downstream scoring |
| Retrieval integration | Use actual BM25 scores instead of positional approximation |

**What this step does NOT cover**:
- Embeddings or vector search (step 19b)
- Hybrid scoring rewrite (step 19c)
- Frontend search UI changes

---

## File Changes

```
backend/
  services/
    memory_service.py          # MODIFY — BM25 ranking + OR fallback
  services/
    retrieval.py               # MODIFY — use _bm25_score from candidates
  tests/
    test_bm25_ranking.py       # NEW — verify ranking order
```

---

## Implementation Details

### 1. `memory_service.list_notes()` — BM25 Ranking

```python
async def list_notes(
    folder: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    workspace_path: Optional[Path] = None,
) -> List[Dict]:
    db_p = _db_path(workspace_path)
    if not db_p.exists():
        return []

    async with aiosqlite.connect(str(db_p)) as db:
        db.row_factory = aiosqlite.Row
        if search:
            tokens = re.findall(r'\w+', search)[:8]
            if not tokens:
                return []

            # Column weights: title 10×, body 1×, tags 5×
            bm25_expr = "bm25(notes_fts, 10.0, 1.0, 5.0)"

            # Try AND first (all terms required)
            fts_and = " ".join(t + "*" for t in tokens)
            query = f"""
                SELECT n.path, n.title, n.folder, n.tags,
                       n.updated_at, n.word_count,
                       {bm25_expr} AS bm25_score
                FROM notes n
                JOIN notes_fts ON notes_fts.rowid = n.id
                WHERE notes_fts MATCH ?
                ORDER BY bm25_score
                LIMIT ?
            """
            # Note: bm25() returns negative values (lower = better match)
            # so ORDER BY bm25_score ascending = best matches first
            params: list = [fts_and]
            if folder:
                # Add folder filter as subquery to preserve ranking
                query = f"""
                    SELECT n.path, n.title, n.folder, n.tags,
                           n.updated_at, n.word_count,
                           {bm25_expr} AS bm25_score
                    FROM notes n
                    JOIN notes_fts ON notes_fts.rowid = n.id
                    WHERE notes_fts MATCH ? AND n.folder = ?
                    ORDER BY bm25_score
                    LIMIT ?
                """
                params.append(folder)
            params.append(limit)

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            # Fallback to OR if AND returns < 3 results and we have 2+ tokens
            if len(rows) < 3 and len(tokens) >= 2:
                fts_or = " OR ".join(t + "*" for t in tokens)
                params[0] = fts_or
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()

            # ... build results with _bm25_score field ...
```

### 2. `retrieval.py` — Use Real BM25 Scores

Replace the positional approximation:
```python
# Before (positional guess):
fts_rank = 1.0 / (i + 1)

# After (real BM25, normalized):
raw_bm25 = abs(candidate.get("_bm25_score", 0))
max_bm25 = max(abs(c.get("_bm25_score", 0)) for c in candidates) or 1.0
fts_rank = raw_bm25 / max_bm25  # normalize to [0, 1]
```

### 3. OR Fallback Strategy

1. Build AND query: `vacation* plan*` — requires both terms
2. If AND returns ≥ 3 results → use them
3. If AND returns < 3 results → try OR: `vacation* OR plan*`
4. This gives precise results when possible, broad results when needed

---

## Test Cases

```python
# test_bm25_ranking.py

async def test_title_match_ranks_higher_than_body():
    """Note with search term in title should outrank body-only match."""

async def test_bm25_order_not_date_order():
    """Old but relevant note should outrank new but tangential note."""

async def test_or_fallback_when_and_too_few():
    """If AND match returns < 3 results, OR query broadens results."""

async def test_bm25_score_returned():
    """Search results include _bm25_score for downstream use."""
```

---

## Acceptance Criteria

- [ ] `list_notes(search="vacation")` returns results sorted by relevance, not date
- [ ] A note titled "Vacation Plans" ranks above a note mentioning "vacation" once in body
- [ ] `_bm25_score` field available in results when search is used
- [ ] `retrieval.py` uses real BM25 scores instead of `1/(i+1)` positional guess
- [ ] Existing tests pass (no regressions)
- [ ] New tests for BM25 ranking and OR fallback
