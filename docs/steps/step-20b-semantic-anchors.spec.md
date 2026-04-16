# Step 20b — Semantic Graph Anchors + Node Embeddings

> **Goal**: Replace substring-based graph anchor matching with semantic matching.
> Embed graph node labels so that query "what did Michał say about the website"
> finds `person:Michał Kowalski` even without exact substring match.
> Extend anchoring to all node types, not just person/tag/area.

**Status**: ⬜ Not started
**Depends on**: Step 20a (embedding infrastructure for chunks)
**Effort**: ~1 day

---

## Why This Matters

Today's anchor matching (`retrieval.py:23-31`):

```python
def _extract_query_entities(query: str, graph: Graph) -> List[str]:
    query_lower = query.lower()
    matches = []
    for node in graph.nodes.values():
        if node.type in ("person", "tag", "area"):
            if node.label.lower() in query_lower:
                matches.append(node.id)
    return matches
```

Problems:
1. **Substring only** — "Michał" matches but "Kowalski" alone doesn't find `person:Michał Kowalski`
2. **Limited types** — only `person`, `tag`, `area`; misses `project`, `source`, `topic` nodes
3. **No semantic understanding** — "vacation" doesn't match node labeled "Trip to Italy"
4. **No fuzzy matching** — typos, abbreviations, partial names fail silently

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `node_embeddings` table | Store embeddings for every graph node label |
| `embed_graph_nodes()` | Embed all node labels in batch |
| `_semantic_anchor_match()` | Find top-K nodes by cosine similarity to query embedding |
| Replace `_extract_query_entities()` | New function uses semantic matching + substring fallback |
| All node types | Anchoring works for note, person, tag, area, project — everything |
| Incremental update | When graph changes, only embed new/changed nodes |

**What this step does NOT cover**:
- Node "profiles" (text summaries of nodes) — just labels for now
- Edge creation from node embeddings (step 20c)

---

## File Structure

```
backend/
  services/
    embedding_service.py     # MODIFY — add node embedding functions
    retrieval.py             # MODIFY — replace _extract_query_entities
    graph_service.py         # MODIFY — trigger node embedding on rebuild
  models/
    database.py              # MODIFY — add node_embeddings table
  tests/
    test_semantic_anchors.py # NEW — semantic anchor matching tests
```

---

## Schema Changes (`database.py`)

```sql
CREATE TABLE IF NOT EXISTS node_embeddings (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    embedding BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    model_name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedded_at TEXT NOT NULL
);
```

**Why separate from `note_embeddings` / `chunk_embeddings`**:
- Node IDs are strings (`person:Michał Kowalski`), not integers
- Nodes have types (person, tag, area, project)
- This is a different granularity — node labels, not document content
- Keeps queries simple and avoids mixing concerns

---

## Implementation Details

### 1. `embedding_service.py` — Node Embedding Functions

```python
async def embed_graph_nodes(
    graph_nodes: list[dict],  # [{"id": "person:Michał", "type": "person", "label": "Michał Kowalski"}, ...]
    db_path: Path,
) -> int:
    """Embed graph node labels in batch. Returns count of newly embedded nodes."""
    # Filter to nodes worth embedding (skip very short labels)
    embeddable = [n for n in graph_nodes if len(n["label"]) >= 2]
    if not embeddable:
        return 0

    # Batch embed all labels
    texts = [n["label"] for n in embeddable]
    vectors = embed_texts(texts)

    async with aiosqlite.connect(str(db_path)) as db:
        count = 0
        for node, vec in zip(embeddable, vectors):
            c_hash = content_hash(node["label"])

            # Check if already embedded with same label
            cursor = await db.execute(
                "SELECT content_hash FROM node_embeddings WHERE node_id = ?",
                (node["id"],),
            )
            row = await cursor.fetchone()
            if row and row[0] == c_hash:
                continue  # unchanged

            blob = vector_to_blob(vec)
            now = datetime.now(timezone.utc).isoformat()
            await db.execute("""
                INSERT OR REPLACE INTO node_embeddings
                (node_id, node_type, label, embedding, content_hash, model_name, dimensions, embedded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (node["id"], node["type"], node["label"], blob, c_hash, _MODEL_NAME, _DIMENSIONS, now))
            count += 1

        await db.commit()
    return count


async def find_similar_nodes(
    query: str,
    limit: int = 5,
    node_types: list[str] | None = None,
    workspace_path: Path | None = None,
) -> list[tuple[str, str, float]]:
    """Find graph nodes whose labels are semantically similar to query.

    Returns: [(node_id, label, similarity_score), ...]
    """
    db_path = (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    query_vec = embed_query(query)

    async with aiosqlite.connect(str(db_path)) as db:
        if node_types:
            placeholders = ",".join("?" * len(node_types))
            cursor = await db.execute(
                f"SELECT node_id, label, embedding FROM node_embeddings WHERE node_type IN ({placeholders})",
                node_types,
            )
        else:
            cursor = await db.execute("SELECT node_id, label, embedding FROM node_embeddings")
        rows = await cursor.fetchall()

    scored = []
    for node_id, label, blob in rows:
        vec = blob_to_vector(blob)
        sim = cosine_similarity(query_vec, vec)
        scored.append((node_id, label, sim))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:limit]
```

### 2. `retrieval.py` — Replace `_extract_query_entities`

```python
# Threshold for semantic anchor matching
_ANCHOR_SIMILARITY_THRESHOLD = 0.50
_MAX_SEMANTIC_ANCHORS = 5


async def _extract_query_anchors(
    query: str,
    graph: graph_service.Graph,
    workspace_path=None,
) -> List[str]:
    """Find graph nodes relevant to the query.

    Strategy:
    1. Try semantic matching (node embeddings) — covers synonyms, partial names
    2. Fall back to substring matching if no node embeddings available
    3. Merge results from both, deduplicating
    """
    anchors: List[str] = []

    # Semantic matching (if node embeddings exist)
    try:
        from services.embedding_service import find_similar_nodes, is_available
        if is_available():
            similar = await find_similar_nodes(
                query, limit=_MAX_SEMANTIC_ANCHORS, workspace_path=workspace_path,
            )
            for node_id, label, score in similar:
                if score >= _ANCHOR_SIMILARITY_THRESHOLD and node_id in graph.nodes:
                    anchors.append(node_id)
    except (ImportError, Exception):
        pass

    # Substring fallback (always runs — catches exact matches semantic might miss)
    query_lower = query.lower()
    for node in graph.nodes.values():
        if node.label.lower() in query_lower and node.id not in anchors:
            anchors.append(node.id)

    return anchors[:_MAX_SEMANTIC_ANCHORS]
```

**Key change**: This function is now `async` because it calls `find_similar_nodes`.
The call site in `retrieve()` must await it:

```python
# Old (sync):
anchors = _extract_query_entities(query, graph)

# New (async):
anchors = await _extract_query_anchors(query, graph, workspace_path)
```

### 3. `graph_service.py` — Trigger Node Embedding on Rebuild

At the end of `rebuild_graph()`, after graph is built:

```python
# Pass 8: Embed node labels for semantic anchoring
import os
if os.environ.get("JARVIS_DISABLE_EMBEDDINGS") != "1":
    try:
        from services.embedding_service import embed_graph_nodes
        import asyncio
        nodes_data = [
            {"id": n.id, "type": n.type, "label": n.label}
            for n in graph.nodes.values()
        ]
        db_path = (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"
        # Run async embed in sync context (rebuild_graph is sync)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(embed_graph_nodes(nodes_data, db_path))
        else:
            asyncio.run(embed_graph_nodes(nodes_data, db_path))
    except (ImportError, Exception) as exc:
        logger.debug("Node embedding skipped: %s", exc)
```

**Note**: `rebuild_graph` is currently synchronous. We use `ensure_future` to
schedule node embedding without blocking the rebuild. This is acceptable because
node embeddings are a derived cache — if they're slightly delayed, the next
search will pick them up.

---

## Anchor Matching: Before vs After

| Query | Before (substring) | After (semantic) |
|-------|-------------------|------------------|
| "what did Michał say" | ✅ finds `person:Michał Kowalski` | ✅ finds `person:Michał Kowalski` |
| "Kowalski's opinion" | ❌ substring "Kowalski" not in node label as standalone | ✅ cosine("Kowalski", "Michał Kowalski") > 0.5 |
| "trip to Italy" | ❌ no node labeled exactly "trip to Italy" | ✅ finds `note:travel/italy-2026.md` by semantic similarity |
| "sleep improvement" | ❌ no tag/person with "sleep improvement" | ✅ finds `tag:health`, `tag:sleep`, `area:health` |
| "website project" | ❌ not a person/tag/area type | ✅ all node types searched — finds `note:projects/website.md` |

---

## Test Cases

```python
# test_semantic_anchors.py

async def test_semantic_anchor_finds_partial_name():
    """Query 'Kowalski' should anchor to person:Michał Kowalski."""

async def test_semantic_anchor_finds_synonym():
    """Query about 'vacation' anchors to tag:travel or note about trips."""

async def test_semantic_anchor_all_node_types():
    """Anchors found for person, tag, area, and note nodes."""

async def test_substring_fallback_when_no_embeddings():
    """Without node_embeddings, falls back to substring match."""

async def test_anchor_threshold_filters_low_similarity():
    """Nodes below _ANCHOR_SIMILARITY_THRESHOLD are excluded."""

async def test_max_anchors_capped():
    """At most _MAX_SEMANTIC_ANCHORS returned."""

async def test_anchor_dedup_between_semantic_and_substring():
    """Same node found by both methods appears only once."""

async def test_embed_graph_nodes_batch():
    """embed_graph_nodes processes all nodes in one batch."""

async def test_embed_graph_nodes_skips_unchanged():
    """Re-embedding with same labels skips already-embedded nodes."""
```

---

## Acceptance Criteria

- [ ] `node_embeddings` table created on startup
- [ ] `embed_graph_nodes()` embeds all graph node labels in batch
- [ ] `find_similar_nodes()` returns nodes ranked by cosine similarity
- [ ] `_extract_query_anchors()` replaces `_extract_query_entities()` in retrieval
- [ ] Anchoring works for all node types (note, person, tag, area, project)
- [ ] Substring matching remains as fallback
- [ ] `rebuild_graph()` triggers node embedding
- [ ] All new tests pass
- [ ] All existing retrieval tests pass (no regressions)
- [ ] Re-run eval set: relational query recall should improve vs post-20a baseline
