# Step 13 — Graph-Guided Retrieval

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 12 — Interactive Graph UX](step-12-graph-interactive.md) | **Next**: [Step 14 — Smart Edge Quality](step-14-smart-edges.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Replace the current flat FTS+neighbor retrieval with a weighted, graph-aware pipeline that selects fewer, more relevant notes for Claude's context. Key outcomes: better answer quality and measurable token savings (target: 30-50% fewer context tokens for graph-connected queries).

---

## Dependencies

No new packages. Pure algorithmic improvements to existing retrieval and graph services.

---

## Files to Create / Modify

### Backend
```
backend/
├── services/
│   ├── retrieval.py             # REWRITE — weighted graph-aware retrieval
│   ├── graph_service.py         # MODIFY — add edge weights, IDF, path scoring, cluster detection
│   ├── context_builder.py       # MODIFY — use cluster-aware deduplication
│   └── token_tracking.py        # MODIFY — log context_tokens for before/after comparison
├── tests/
│   ├── test_graph_retrieval.py  # MODIFY — expand with weight and ranking tests
│   └── test_retrieval.py        # NEW — dedicated tests for new retrieval pipeline
```

---

## Specification

### A. Edge Weights

Currently all edges are binary (exist or don't). Add a `weight` field to edges that encodes signal strength.

**Weight assignment rules:**

| Edge type | Base weight | Modifier |
|-----------|------------|----------|
| `linked` (wiki-link) | 1.0 | Bidirectional links get 1.2 |
| `related` (frontmatter) | 0.9 | — |
| `mentions` (person) | 0.8 | — |
| `tagged` | 0.6 | Multiplied by IDF factor (see below) |
| `part_of` (folder) | 0.3 | — |
| `similar_to` (step 14) | 0.5 | Based on keyword overlap score |
| `temporal` (step 14) | 0.2 | — |

**Implementation:**

```python
@dataclass(eq=True, frozen=True)
class Edge:
    source: str
    target: str
    type: str
    weight: float = 1.0
```

Graph JSON format gains a `weight` field per edge. Existing graphs without weights default to 1.0.

---

### B. Tag Inverse Document Frequency (IDF)

Tags that appear on many notes carry less information. A tag connecting 2 notes is a strong signal; a tag connecting 50 is noise.

```python
import math

def compute_tag_idf(graph: Graph) -> dict[str, float]:
    """Compute IDF score for each tag node.

    IDF = log(total_notes / notes_with_this_tag)
    Normalized to [0, 1] range.
    """
    note_count = sum(1 for n in graph.nodes.values() if n.type == "note")
    if note_count == 0:
        return {}

    tag_freq: dict[str, int] = {}
    for edge in graph.edges:
        if edge.type == "tagged":
            tag_id = edge.target if edge.target.startswith("tag:") else edge.source
            tag_freq[tag_id] = tag_freq.get(tag_id, 0) + 1

    max_idf = math.log(note_count + 1)  # for normalization
    idf = {}
    for tag_id, freq in tag_freq.items():
        raw = math.log((note_count + 1) / (freq + 1))
        idf[tag_id] = round(raw / max_idf, 3) if max_idf > 0 else 0.5

    return idf
```

**Applied during graph rebuild:** Each `tagged` edge gets `weight = 0.6 * idf[tag_id]`.

Result: `tag:python` (on 40 notes) gets weight ~0.12. `tag:space-economy` (on 3 notes) gets weight ~0.52. Retrieval naturally prefers the specific tag.

---

### C. Weighted Graph Expansion in Retrieval

Replace the current flat neighbor expansion with a weighted walk.

**Current behavior:**
```
FTS results → take top 3 → get_neighbors(depth=1) → merge → return
```

**New behavior:**
```
FTS results (scored by FTS rank)
    │
    ▼
For each FTS hit, compute graph_score:
  - Sum of edge weights on paths to query-relevant nodes
  - Boost for nodes connected to multiple FTS hits (convergence bonus)
    │
    ▼
Weighted merge:
  - final_score = fts_rank * 0.6 + graph_score * 0.4
    │
    ▼
Cluster deduplication:
  - Group by connected component
  - If 3 notes from same cluster, keep top 2
    │
    ▼
Return top N (default 5)
```

**Implementation:**

```python
async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> list[dict]:
    """Weighted hybrid retrieval: FTS + graph scoring + cluster dedup."""
    if not query or not query.strip():
        return []

    # 1. FTS search (get more candidates than needed)
    candidates = await memory_service.list_notes(
        search=query,
        limit=limit * 3,
        workspace_path=workspace_path,
    )

    # 2. Load graph for scoring
    graph = graph_service.load_graph(workspace_path)
    if not graph:
        return candidates[:limit]

    # 3. Score each candidate using graph neighborhood
    scored = []
    fts_node_ids = {f"note:{c['path']}" for c in candidates}

    for i, candidate in enumerate(candidates):
        node_id = f"note:{candidate['path']}"
        fts_rank = 1.0 / (i + 1)  # Reciprocal rank from FTS order

        # Graph score: weighted sum of edges to other FTS hits
        graph_score = 0.0
        if node_id in graph.nodes:
            for edge in graph.edges:
                if edge.source == node_id and edge.target in fts_node_ids:
                    graph_score += edge.weight
                elif edge.target == node_id and edge.source in fts_node_ids:
                    graph_score += edge.weight

            # Convergence bonus: node connects to 3+ FTS hits
            neighbor_ids = {e.target for e in graph.edges if e.source == node_id}
            neighbor_ids |= {e.source for e in graph.edges if e.target == node_id}
            overlap = len(neighbor_ids & fts_node_ids)
            if overlap >= 3:
                graph_score += 0.3

        final_score = fts_rank * 0.6 + graph_score * 0.4
        scored.append({**candidate, "_score": final_score, "_node_id": node_id})

    # 4. Sort by final score
    scored.sort(key=lambda x: x["_score"], reverse=True)

    # 5. Cluster dedup: avoid returning 3+ notes from same folder/cluster
    seen_folders: dict[str, int] = {}
    result = []
    for item in scored:
        folder = item.get("folder", "")
        if folder and seen_folders.get(folder, 0) >= 2:
            continue
        seen_folders[folder] = seen_folders.get(folder, 0) + 1
        result.append(item)
        if len(result) >= limit:
            break

    # Clean internal fields
    for r in result:
        r.pop("_score", None)
        r.pop("_node_id", None)

    return result
```

---

### D. Path Scoring for Relationship Queries

When the user asks "What did I promise Michał about project X?", the system should find notes connected via paths through both `person:Michał` AND `tag:project-x`.

**Path scoring algorithm:**

```python
def score_by_path(
    graph: Graph,
    anchor_nodes: list[str],
    candidate_id: str,
    max_depth: int = 3,
) -> float:
    """Score a candidate note by shortest weighted paths to anchor nodes.

    anchor_nodes: entities extracted from the query (e.g. ['person:Michał', 'tag:project-x'])
    Returns higher score if candidate is close to multiple anchors.
    """
    total = 0.0
    for anchor in anchor_nodes:
        dist = _shortest_weighted_path(graph, candidate_id, anchor, max_depth)
        if dist is not None:
            total += 1.0 / (1.0 + dist)  # closer = higher score
    return total
```

**Query entity extraction** (simple, no API call):

```python
def extract_query_entities(query: str, graph: Graph) -> list[str]:
    """Match query tokens against known graph node labels."""
    query_lower = query.lower()
    matches = []
    for node in graph.nodes.values():
        if node.type in ("person", "tag", "area"):
            if node.label.lower() in query_lower:
                matches.append(node.id)
    return matches
```

If anchors are found, path scoring is blended into the retrieval:
```
final_score = fts_rank * 0.4 + graph_score * 0.3 + path_score * 0.3
```

---

### E. Context Token Tracking

To measure improvement, log how many context tokens are sent to Claude before and after this change.

Add to `token_tracking.py`:
```python
def log_usage(
    input_tokens: int,
    output_tokens: int,
    context_tokens: int = 0,    # NEW — tokens from retrieved notes
    ...
```

Add to `context_builder.py`:
```python
# After building context, estimate tokens:
context_token_estimate = len(context_text) // 4  # rough char-to-token ratio
```

This lets the settings page show: "Average context tokens per query: X" and track improvement over time.

---

## Tests

### Backend
```
test_tag_idf_computation          — verify IDF scores: rare tag > common tag
test_tag_idf_single_note          — edge case: only one note in graph
test_edge_weight_assignment       — verify rebuild sets correct weights per type
test_weighted_retrieval_prefers_specific — tag with IDF 0.5 beats tag with IDF 0.1
test_weighted_retrieval_convergence    — note linked to multiple FTS hits ranks higher
test_cluster_dedup                — verify max 2 notes per folder in results
test_path_scoring_two_anchors     — note reachable from both person + tag ranks highest
test_query_entity_extraction      — verify person and tag labels matched from query
test_retrieval_no_graph_fallback  — with no graph, falls back to pure FTS
test_context_token_logging        — verify context_tokens field in usage log
```

---

## Definition of Done

- [ ] Edges have `weight` field, assigned by type + IDF for tags
- [ ] Tag IDF computed during graph rebuild
- [ ] Retrieval uses weighted scoring: FTS rank × 0.6 + graph score × 0.4
- [ ] Path scoring activates when query mentions known entities
- [ ] Cluster dedup limits per-folder results to avoid redundancy
- [ ] Context tokens logged for before/after comparison
- [ ] All tests pass
- [ ] Documentation updated
