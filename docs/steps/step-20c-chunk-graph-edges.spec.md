# Step 20c — Chunk-Level Graph Linking with Evidence

> **Goal**: Replace note↔note `similar_to` edges with chunk↔chunk similarity
> that points to **specific evidence** for why two notes are related.
> Graph edges gain `evidence_chunk_ids` and more granular weights.

**Status**: ⬜ Not started
**Depends on**: Step 20a (chunk_embeddings table exists and populated)
**Effort**: ~1.5 days

---

## Why This Matters

Today (`graph_service.py:233-298`):
- `similar_to` edges connect **whole notes** based on note-level embedding similarity
- Threshold: cosine ≥ 0.65, max 5 edges per node
- Weight mapped linearly from `[0.65, 1.0]` → `[0.3, 1.0]`

Problems:
1. **Coarse granularity**: A long note about 5 topics gets one vector. Two notes
   that share one paragraph about sleep but are otherwise unrelated get a low
   note-level similarity — the connection is invisible.
2. **No evidence**: When `similar_to` edge exists, there's no way to know *why*.
   Which section matches which? What's the actual overlap?
3. **False positives**: Two long notes on vaguely similar broad topics get connected
   even though no specific section actually overlaps.

After this step:
- `similar_to` edges are built from **chunk-pair similarity**
- Each edge stores `evidence_chunks`: which specific chunks matched
- The graph can answer "why are these connected?" with concrete text spans
- Better precision: specific sections must match, not just overall vibes

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Chunk-pair similarity scanning | Compare chunks across notes, find strong matches |
| Evidence-backed edges | Each `similar_to` edge stores chunk IDs that justify it |
| Better edge weights | Derived from best chunk-pair similarity, not note-level average |
| Updated `Edge` model | Add optional `evidence` field to Edge dataclass |
| Updated graph visualization data | `to_dict()` includes evidence metadata |
| Fallback to note-level | If no chunks available, existing note-level similarity still works |

**What this step does NOT cover**:
- Typed relations (supports/contradicts/explains) — needs LLM, deferred
- Cross-type edges (person↔topic) — step after this
- Reranking — step 20e

---

## File Structure

```
backend/
  services/
    graph_service.py         # MODIFY — chunk-based similarity edges
  tests/
    test_chunk_graph_edges.py # NEW — chunk-level edge building tests
```

---

## Implementation Details

### 1. Updated `Edge` Dataclass

```python
@dataclass(eq=True, frozen=True)
class Edge:
    source: str
    target: str
    type: str
    weight: float = 1.0
    evidence: tuple = ()  # ((source_chunk_idx, target_chunk_idx, similarity), ...)
```

**Why `tuple` not `list`**: Edge is frozen+hashable. Tuples are hashable.

**`to_dict()` change**:
```python
def to_dict(self) -> Dict:
    return {
        "nodes": [...],
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "type": e.type,
                "weight": e.weight,
                **({"evidence": [
                    {"source_chunk": sc, "target_chunk": tc, "similarity": round(sim, 3)}
                    for sc, tc, sim in e.evidence
                ]} if e.evidence else {}),
            }
            for e in self.edges
        ],
    }
```

### 2. `_compute_chunk_similarity_edges()` — New Function

Replaces `_compute_embedding_similarity_edges()` when chunks are available:

```python
def _compute_chunk_similarity_edges(
    graph: Graph,
    memory_path: Path,
) -> List[Edge]:
    """Build similar_to edges from chunk-pair cosine similarity.

    For each pair of notes (A, B):
    1. Find the best matching chunk pair (chunk_A_i, chunk_B_j)
    2. If best_sim >= threshold → create edge with evidence
    3. Edge weight = best chunk-pair similarity mapped to [0.3, 1.0]
    """
    import sqlite3
    from services.embedding_service import blob_to_vector, cosine_similarity

    ws = memory_path.parent
    db_path = ws / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            "SELECT ce.path, ce.chunk_index, ce.embedding "
            "FROM chunk_embeddings ce"
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if len(rows) < 2:
        return []

    # Group chunks by note path
    graph_paths = {n.id[5:] for n in graph.nodes.values() if n.type == "note"}
    note_chunks: Dict[str, List[tuple]] = {}
    for path, idx, blob in rows:
        if path in graph_paths:
            vec = blob_to_vector(blob)
            note_chunks.setdefault(path, []).append((idx, vec))

    paths = list(note_chunks.keys())
    if len(paths) < 2:
        return []

    # Pairwise comparison: for each note pair, find best chunk match
    CHUNK_SIM_THRESHOLD = 0.70  # Higher than note-level (0.65) because chunks are more specific
    MAX_EDGES_PER_NODE = 5
    MAX_EVIDENCE_PER_EDGE = 3

    new_edges: List[Edge] = []
    edge_count: Dict[str, int] = {}

    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            path_a, path_b = paths[i], paths[j]
            node_a, node_b = f"note:{path_a}", f"note:{path_b}"

            if edge_count.get(node_a, 0) >= MAX_EDGES_PER_NODE:
                continue
            if edge_count.get(node_b, 0) >= MAX_EDGES_PER_NODE:
                continue

            # Find best chunk pairs
            chunk_pairs = []
            for idx_a, vec_a in note_chunks[path_a]:
                for idx_b, vec_b in note_chunks[path_b]:
                    sim = cosine_similarity(vec_a, vec_b)
                    if sim >= CHUNK_SIM_THRESHOLD:
                        chunk_pairs.append((idx_a, idx_b, sim))

            if not chunk_pairs:
                continue

            # Sort by similarity, take top evidence
            chunk_pairs.sort(key=lambda x: x[2], reverse=True)
            best_sim = chunk_pairs[0][2]
            evidence = tuple(chunk_pairs[:MAX_EVIDENCE_PER_EDGE])

            # Map [0.70, 1.0] → [0.3, 1.0]
            weight = min(round(0.3 + (best_sim - 0.70) * (0.7 / 0.30), 3), 1.0)

            new_edges.append(Edge(
                source=node_a,
                target=node_b,
                type="similar_to",
                weight=weight,
                evidence=evidence,
            ))
            edge_count[node_a] = edge_count.get(node_a, 0) + 1
            edge_count[node_b] = edge_count.get(node_b, 0) + 1

    return new_edges
```

### 3. Updated `_compute_similarity_edges()` — Cascade Strategy

```python
def _compute_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Compute similar_to edges using best available strategy.

    Priority:
    1. Chunk-level embeddings (most precise)
    2. Note-level embeddings (existing fallback)
    3. Keyword Jaccard (legacy fallback)
    """
    # Try chunk-level first
    try:
        chunk_edges = _compute_chunk_similarity_edges(graph, memory_path)
        if chunk_edges:
            return chunk_edges
    except Exception:
        pass

    # Fall back to note-level embeddings
    try:
        note_edges = _compute_embedding_similarity_edges(graph, memory_path)
        if note_edges:
            return note_edges
    except Exception:
        pass

    # Last resort: keyword Jaccard
    return _compute_keyword_similarity_edges(graph, memory_path)
```

### 4. Performance Consideration

Chunk-pair comparison is O(N² × C²) where N = notes, C = avg chunks per note.
For 200 notes × 5 chunks = 1000 chunks, that's ~500K comparisons.
At 384-dim cosine with numpy: ~0.01ms per comparison → ~5 seconds total.

**Optimization**: Pre-filter by only comparing chunks within same topic cluster
(e.g., same folder or shared tag). But for MVP scale this is fine.

If it becomes slow (>30s), add:
```python
# Pre-filter: only compare notes that share at least one tag or folder
# This reduces N² to much smaller set
```

---

## Edge Quality: Before vs After

| Scenario | Before (note-level) | After (chunk-level) |
|----------|---------------------|---------------------|
| Two notes, each with one paragraph about sleep | Note-level sim: 0.45 (no edge) | Chunk-level sim of sleep paragraphs: 0.82 (edge created!) |
| Two long project notes, vaguely similar overall | Note-level sim: 0.68 (edge created) | Best chunk pair: 0.55 (no edge — they're actually different) |
| Note A section 2 ↔ Note B section 4 specifically match | Edge exists but no idea why | Evidence: `[{source_chunk: 2, target_chunk: 4, sim: 0.85}]` |

---

## Graph Visualization Impact

The frontend `GraphCanvas.vue` already renders `similar_to` edges with dashed lines.
With evidence metadata, a future tooltip can show:
- "Connected because: section 'Meeting Notes' ↔ section 'Project Updates' (85% similar)"

This step just provides the data. Frontend changes are optional and out of scope.

---

## Test Cases

```python
# test_chunk_graph_edges.py

async def test_chunk_edges_created_above_threshold():
    """Two notes with similar chunks (>= 0.70) get a similar_to edge."""

async def test_chunk_edges_not_created_below_threshold():
    """Notes with only chunk similarity < 0.70 get no edge."""

async def test_evidence_stored_on_edge():
    """Edge.evidence contains (source_chunk_idx, target_chunk_idx, similarity)."""

async def test_edge_weight_from_best_chunk_pair():
    """Edge weight derived from best chunk pair, not average."""

async def test_max_evidence_per_edge():
    """At most MAX_EVIDENCE_PER_EDGE chunk pairs stored."""

async def test_max_edges_per_node():
    """No node exceeds MAX_EDGES_PER_NODE similar_to edges."""

async def test_fallback_to_note_level():
    """When chunk_embeddings table is empty, falls back to note-level."""

async def test_fallback_to_keyword():
    """When both chunk and note embeddings are empty, uses keyword Jaccard."""

async def test_to_dict_includes_evidence():
    """graph.to_dict() serializes evidence for similar_to edges."""

async def test_rebuild_graph_uses_chunk_edges():
    """Full rebuild_graph uses chunk similarity when chunks are populated."""
```

---

## Acceptance Criteria

- [ ] `_compute_chunk_similarity_edges()` creates edges from chunk-pair similarity
- [ ] Chunk similarity threshold: 0.70 (stricter than note-level 0.65)
- [ ] Each edge stores `evidence` with up to 3 best chunk pairs
- [ ] `Edge` dataclass extended with `evidence: tuple`
- [ ] `to_dict()` serializes evidence in graph JSON
- [ ] `_compute_similarity_edges()` cascades: chunk → note → keyword
- [ ] Max 5 `similar_to` edges per node maintained
- [ ] Edge weight derived from best chunk pair similarity
- [ ] All existing graph tests pass (backwards compatible)
- [ ] All new tests pass
- [ ] Pairwise comparison completes in <10s for 200 notes (benchmark)
