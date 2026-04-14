# Step 19c — Hybrid Retrieval + Graph-Semantic Integration

> **Goal**: Combine BM25, vector similarity, and graph signals into a single
> unified retrieval pipeline. Use embeddings to create semantic edges in the
> knowledge graph. Make the whole system smarter together than any part alone.

**Status**: ⬜ Not started
**Depends on**: Step 19a (BM25 fix) + Step 19b (local embeddings)
**Effort**: ~4–6 hours

---

## Why This Matters

This is the step that makes Jarvis a **real knowledge system** — not just
a file search or a chatbot with memory.

Three retrieval signals individually:
- **BM25**: finds notes with matching keywords (fast, precise, brittle)
- **Cosine similarity**: finds notes with matching meaning (flexible, fuzzy)
- **Graph**: finds notes connected through relationships (structural, contextual)

Each has blind spots. Combined, they cover each other's weaknesses:

| Query | BM25 finds | Embeddings find | Graph finds |
|-------|-----------|-----------------|-------------|
| "vacation plans" | Notes mentioning "vacation" | Notes about travel, PTO, summer trips | Notes linked to [Trip to Italy] or tagged #travel |
| "what did Michał say about the project" | Notes with "Michał" + "project" | Notes about team discussions, decisions | People node [Michał] → linked notes, project edges |
| "how to improve my sleep" | Notes with "sleep" | Notes about evening routines, circadian rhythm, melatonin | Health area → knowledge sources about sleep |

The graph layer is especially powerful because it captures **structure**
the user explicitly created: links between notes, people mentioned,
areas of life, projects. This step makes the graph not just a visualization
but an active part of how Jarvis retrieves and reasons about knowledge.

---

## Core Principles

1. **Weighted fusion** — each signal contributes a normalized [0,1] score
2. **Tunable weights** — default `0.35 BM25 + 0.35 cosine + 0.30 graph`, adjustable
3. **Graceful degradation** — if embeddings unavailable, falls back to BM25 + graph
4. **Graph gets smarter** — embedding similarity creates new `similar_to` edges
5. **Semantic clusters** — groups of semantically related notes become visible in graph UI

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Hybrid scoring rewrite | `retrieval.py` combines 3 normalized signals |
| Semantic graph edges | Embedding similarity → `similar_to` edges (replaces keyword Jaccard) |
| Graph-aware re-ranking | Notes connected to multiple query-relevant nodes get boosted |
| Retrieval metadata | Response includes which signals contributed (for debugging/transparency) |
| Semantic search API | `GET /api/memory/semantic-search?q=...` standalone endpoint |
| Frontend search mode | Toggle between keyword / semantic / hybrid in search UI |
| Embedding-based graph rebuild | `rebuild_graph()` uses embeddings for `similar_to` edges |

**What this step does NOT cover**:
- Vector database migration (not needed at this scale)
- Multi-modal embeddings (images, PDFs)
- Automatic specialist routing based on query embeddings

---

## File Structure

```
backend/
  services/
    retrieval.py               # MODIFY — hybrid scoring with 3 signals
    graph_service.py           # MODIFY — embedding-based similar_to edges
    embedding_service.py       # MODIFY — add batch similarity for graph
  routers/
    memory.py                  # MODIFY — add semantic search endpoint
  tests/
    test_hybrid_retrieval.py   # NEW — test 3-signal fusion
    test_graph_semantic.py     # NEW — test embedding-based edges
frontend/
  app/
    pages/memory.vue           # MODIFY — search mode toggle
    components/GraphCanvas.vue # MODIFY — semantic edge styling
```

---

## Architecture

```
User query: "how to improve my sleep"
    │
    ├──────────────────────────┐
    │                          │
    ▼                          ▼
┌─────────────┐      ┌──────────────────┐
│  BM25 Search │      │  Embed query     │
│  (SQLite FTS)│      │  (local model)   │
└──────┬──────┘      └────────┬─────────┘
       │                      │
       ▼                      ▼
  Candidates           ┌──────────────────┐
  with BM25 score      │  Cosine search   │
       │               │  (all embeddings)│
       │               └────────┬─────────┘
       │                        │
       ▼                        ▼
    ┌───────────────────────────────────┐
    │       Candidate Pool (union)      │
    │  Each note has: bm25 | cosine     │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │     Graph Scoring                 │
    │                                   │
    │  For each candidate:              │
    │  • Edge weight to other hits      │
    │  • Path distance to query anchors │
    │  • Convergence bonus (3+ links)   │
    │  • Cluster membership bonus       │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │     Weighted Fusion               │
    │                                   │
    │  final = w₁·bm25 + w₂·cos + w₃·g│
    │  default: 0.35 + 0.35 + 0.30     │
    │                                   │
    │  Tie-breaker: recency             │
    └───────────────┬───────────────────┘
                    │
                    ▼
    ┌───────────────────────────────────┐
    │     Cluster Dedup + Top-K         │
    │  Max 2 per folder, ≤ limit        │
    └───────────────────────────────────┘
                    │
                    ▼
            Final results with
            _retrieval_signals metadata
```

---

## Implementation Details

### 1. `retrieval.py` — Hybrid Scoring Rewrite

```python
# Default weights (configurable per-specialist later)
WEIGHT_BM25 = 0.35
WEIGHT_COSINE = 0.35
WEIGHT_GRAPH = 0.30

async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> List[Dict]:
    """Hybrid retrieval: BM25 + cosine similarity + graph scoring."""
    if not query or not query.strip():
        return []

    # --- Signal 1: BM25 candidates ---
    fts_candidates = await memory_service.list_notes(
        search=query, limit=limit * 3, workspace_path=workspace_path,
    )
    # Index by path with normalized BM25 score
    candidate_pool: Dict[str, Dict] = {}
    max_bm25 = max(
        (abs(c.get("_bm25_score", 0)) for c in fts_candidates), default=1.0
    ) or 1.0

    for c in fts_candidates:
        path = c["path"]
        bm25_norm = abs(c.get("_bm25_score", 0)) / max_bm25
        candidate_pool[path] = {**c, "_bm25": bm25_norm, "_cosine": 0.0, "_graph": 0.0}

    # --- Signal 2: Cosine similarity (if embeddings available) ---
    cosine_available = False
    try:
        from services.embedding_service import search_similar
        similar = await search_similar(query, limit=limit * 3, workspace_path=workspace_path)
        cosine_available = True

        for path, score in similar:
            if path in candidate_pool:
                candidate_pool[path]["_cosine"] = score
            else:
                # Note found by embeddings but not BM25 — still a candidate
                note_meta = await _get_note_meta(path, workspace_path)
                if note_meta:
                    candidate_pool[path] = {
                        **note_meta, "_bm25": 0.0, "_cosine": score, "_graph": 0.0,
                    }
    except ImportError:
        pass  # fastembed not installed — skip cosine signal

    # --- Signal 3: Graph scoring ---
    graph = graph_service.load_graph(workspace_path)
    if graph:
        anchors = _extract_query_entities(query, graph)
        candidate_ids = {f"note:{p}" for p in candidate_pool}

        for path, data in candidate_pool.items():
            node_id = f"note:{path}"
            graph_score = _compute_graph_score(
                node_id, graph, anchors, candidate_ids,
            )
            data["_graph"] = graph_score

    # --- Weighted fusion ---
    w_bm25 = WEIGHT_BM25
    w_cos = WEIGHT_COSINE if cosine_available else 0.0
    w_graph = WEIGHT_GRAPH if graph else 0.0

    # Re-normalize weights to sum to 1.0
    total_w = w_bm25 + w_cos + w_graph or 1.0
    w_bm25 /= total_w
    w_cos /= total_w
    w_graph /= total_w

    scored = []
    for path, data in candidate_pool.items():
        final = (
            w_bm25 * data["_bm25"]
            + w_cos * data["_cosine"]
            + w_graph * data["_graph"]
        )
        scored.append({
            **data,
            "_score": final,
            "_signals": {
                "bm25": round(data["_bm25"], 3),
                "cosine": round(data["_cosine"], 3),
                "graph": round(data["_graph"], 3),
            },
        })

    scored.sort(key=lambda x: x["_score"], reverse=True)

    # --- Cluster dedup ---
    result = _cluster_dedup(scored, limit)

    # Clean internal fields (keep _signals for debugging)
    for r in result:
        r.pop("_score", None)
        r.pop("_bm25", None)
        r.pop("_cosine", None)
        r.pop("_graph", None)
        r.pop("_bm25_score", None)
        r.pop("_node_id", None)

    return result
```

### 2. Graph Score Function (extracted for clarity)

```python
def _compute_graph_score(
    node_id: str,
    graph: Graph,
    anchors: List[str],
    candidate_ids: Set[str],
) -> float:
    """Combined graph score: edge connectivity + path distance + convergence."""
    if node_id not in graph.nodes:
        return 0.0

    # (a) Edge weight to other candidates in pool
    edge_score = 0.0
    neighbor_ids = set()
    for edge in graph.edges:
        if edge.source == node_id and edge.target in candidate_ids:
            edge_score += edge.weight
            neighbor_ids.add(edge.target)
        elif edge.target == node_id and edge.source in candidate_ids:
            edge_score += edge.weight
            neighbor_ids.add(edge.source)

    # (b) Convergence bonus — connects to 3+ other candidates
    if len(neighbor_ids) >= 3:
        edge_score += 0.3

    # (c) Path distance to query entity anchors
    path_score = 0.0
    if anchors:
        path_score = _score_by_path(graph, anchors, node_id)

    # (d) Semantic cluster bonus — if this node's similar_to neighbors
    # are also in the candidate pool, it's at the center of a topic cluster
    cluster_count = 0
    for edge in graph.edges:
        if edge.type == "similar_to":
            neighbor = edge.target if edge.source == node_id else (
                edge.source if edge.target == node_id else None
            )
            if neighbor and neighbor in candidate_ids:
                cluster_count += 1
    cluster_bonus = min(cluster_count * 0.15, 0.45)

    # Combine and normalize to [0, 1]
    raw = edge_score + path_score + cluster_bonus
    return min(raw, 1.0)
```

### 3. `graph_service.py` — Embedding-Based Similarity Edges

Replace `_compute_similarity_edges()` (currently uses keyword Jaccard) with
embedding cosine similarity:

```python
def _compute_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Compute similar_to edges using embedding cosine similarity.

    Falls back to keyword Jaccard if embeddings not available.
    """
    try:
        return _compute_embedding_similarity_edges(graph, memory_path)
    except (ImportError, Exception):
        return _compute_keyword_similarity_edges(graph, memory_path)


def _compute_embedding_similarity_edges(graph: Graph, memory_path: Path) -> List[Edge]:
    """Use stored embeddings to find semantically similar notes."""
    import aiosqlite
    import asyncio
    from services.embedding_service import blob_to_vector, cosine_similarity

    ws = memory_path.parent  # memory_path = workspace/memory, ws = workspace
    db_path = ws / "app" / "jarvis.db"
    if not db_path.exists():
        raise FileNotFoundError("No database")

    # Load all embeddings
    def _load_sync():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT path, embedding FROM note_embeddings")
        rows = cursor.fetchall()
        conn.close()
        return [(path, blob_to_vector(blob)) for path, blob in rows]

    embeddings = _load_sync()
    if len(embeddings) < 2:
        return []

    # Compute pairwise similarities (only notes in graph)
    graph_paths = {n.id[5:] for n in graph.nodes.values() if n.type == "note"}
    relevant = [(p, v) for p, v in embeddings if p in graph_paths]

    new_edges: List[Edge] = []
    edge_count: Dict[str, int] = {}

    for i in range(len(relevant)):
        for j in range(i + 1, len(relevant)):
            path_a, vec_a = relevant[i]
            path_b, vec_b = relevant[j]
            sim = cosine_similarity(vec_a, vec_b)

            # Threshold: only connect notes with similarity ≥ 0.65
            if sim >= 0.65:
                node_a = f"note:{path_a}"
                node_b = f"note:{path_b}"

                # Cap at 5 similar_to edges per node to avoid hairball
                if edge_count.get(node_a, 0) >= 5 or edge_count.get(node_b, 0) >= 5:
                    continue

                weight = round(0.3 + (sim - 0.65) * 2.0, 3)  # Map [0.65, 1.0] → [0.3, 1.0]
                weight = min(weight, 1.0)
                new_edges.append(Edge(source=node_a, target=node_b, type="similar_to", weight=weight))
                edge_count[node_a] = edge_count.get(node_a, 0) + 1
                edge_count[node_b] = edge_count.get(node_b, 0) + 1

    return new_edges
```

This means the knowledge graph now reflects **semantic** relationships,
not just keyword overlap. Notes about "mindfulness meditation" and
"stress management techniques" will be connected even if they share
zero words.

### 4. Semantic Search API Endpoint

```python
# routers/memory.py

@router.get("/semantic-search")
async def semantic_search(q: str, limit: int = 10):
    """Standalone semantic search — embeddings only, no BM25."""
    try:
        from services.embedding_service import search_similar
        results = await search_similar(q, limit=limit)
        return {
            "results": [
                {"path": path, "similarity": round(score, 3)}
                for path, score in results
            ],
            "mode": "semantic",
        }
    except ImportError:
        return {"results": [], "mode": "unavailable", "error": "fastembed not installed"}
```

### 5. Frontend — Search Mode Toggle

Add to `memory.vue` search bar:

```
[🔍 Keyword] [🧠 Semantic] [⚡ Hybrid]
```

- **Keyword**: current behavior (`/api/memory/notes?search=...`)
- **Semantic**: calls `/api/memory/semantic-search?q=...`
- **Hybrid**: calls `/api/memory/notes?search=...&mode=hybrid` (uses retrieval pipeline)

### 6. Frontend — Semantic Edge Styling in Graph

In `GraphCanvas.vue`, `similar_to` edges rendered differently:
- Dashed line (vs solid for other edge types)
- Color: gradient blue-purple (semantic relationship)
- Tooltip shows similarity score
- Can be toggled on/off in graph controls

---

## How It All Connects: User Scenarios

### Scenario 1: "What did I learn about productivity?"

1. **BM25** finds notes with "productivity" in title/body/tags
2. **Cosine** also finds "Deep Work habits", "Time blocking system", "GTD weekly review" — no keyword match but semantically about productivity
3. **Graph** sees that person:David (David Allen) is connected to GTD note, which links to "Weekly Planning Template"
4. **Fusion**: All three signals converge on "GTD weekly review" → highest score
5. Jarvis gets 5 highly relevant notes as context → answers comprehensively

### Scenario 2: Weekly planning with graph context

1. User says: "Plan my week based on my current projects"
2. **BM25** finds notes with "project" and recent dates
3. **Cosine** finds notes about ongoing work, deadlines, commitments
4. **Graph** traverses `area:work` → project notes, `area:health` → health goals, `area:learning` → courses
5. **Fusion**: Graph signal is strongest here because project structure is explicit
6. Jarvis sees interconnected context → creates a holistic weekly plan

### Scenario 3: Graph visualization reveals hidden connections

1. After embedding all notes, graph rebuild adds `similar_to` edges
2. User opens Graph view and sees:
   - "Evening routine" ←similar_to→ "Sleep quality tracking"
   - "Budget 2025" ←similar_to→ "Investment strategy"
   - "Meditation notes" ←similar_to→ "Stress management"
3. These connections weren't explicit in any note — they emerged from semantic similarity
4. User can click to explore clusters and discover forgotten connections

---

## Retrieval Weights by Context

Different scenarios benefit from different weight distributions.
Future step: let specialists configure their own weights.

| Context | BM25 | Cosine | Graph | Rationale |
|---------|------|--------|-------|-----------|
| Default | 0.35 | 0.35 | 0.30 | Balanced |
| Exact lookup ("find note about X") | 0.60 | 0.20 | 0.20 | Keywords matter most |
| Exploratory ("what do I know about X") | 0.20 | 0.45 | 0.35 | Meaning > keywords |
| Relational ("what connects X to Y") | 0.15 | 0.25 | 0.60 | Graph is king |
| Planning ("plan based on my notes") | 0.25 | 0.30 | 0.45 | Structure matters |

---

## Test Cases

```python
# test_hybrid_retrieval.py

async def test_cosine_adds_non_keyword_results():
    """Candidates found by cosine but not BM25
    still appear in results."""

async def test_graph_boosts_connected_notes():
    """Note linked to query entity via graph scores higher
    than unconnected note with same BM25 score."""

async def test_weight_normalization_without_cosine():
    """If embeddings unavailable, BM25+graph weights
    re-normalize to sum to 1.0."""

async def test_cluster_bonus_in_graph_score():
    """Note at center of similar_to cluster gets bonus."""

async def test_signals_metadata_in_results():
    """Results include _signals dict with per-signal scores."""


# test_graph_semantic.py

async def test_embedding_edges_replace_keyword_edges():
    """similar_to edges use cosine similarity, not keyword Jaccard."""

async def test_similarity_threshold():
    """Only notes with cosine ≥ 0.65 get similar_to edge."""

async def test_edge_cap_per_node():
    """No node gets more than 5 similar_to edges."""

async def test_fallback_to_keyword_similarity():
    """If embeddings unavailable, keyword Jaccard used."""
```

---

## Acceptance Criteria

- [ ] `retrieval.py` combines BM25, cosine, and graph scores with configurable weights
- [ ] Weights auto-normalize when a signal is unavailable (graceful degradation)
- [ ] `_signals` metadata included in retrieval results
- [ ] `_compute_similarity_edges()` uses embedding cosine when available
- [ ] Similarity threshold ≥ 0.65 for `similar_to` graph edges
- [ ] Edge cap of 5 `similar_to` edges per node
- [ ] `GET /api/memory/semantic-search` endpoint works standalone
- [ ] Frontend search has keyword / semantic / hybrid toggle
- [ ] Graph view renders `similar_to` edges with distinct dashed style
- [ ] All existing retrieval tests still pass
- [ ] New hybrid + graph-semantic tests pass
- [ ] System works with embeddings disabled (BM25 + graph only)
