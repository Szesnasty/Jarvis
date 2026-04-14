# Step 14b — Similarity Edges, Temporal Edges, Pruning & Pipeline

> **Goal**: Add keyword-similarity edges, temporal edges (same-day notes),
> prune overloaded tags, and integrate everything into a unified rebuild pipeline.

**Status**: ⬜ Not started
**Depends on**: Step 14a (entity extraction + bidirectional links)

---

## Design Principle: Conservative by Default

> **Risk**: It's easy to over-engineer "smart" heuristics that produce edges that
> look intelligent but are weak or noisy. Every edge type starts **conservative**:
> high thresholds, low weights, easy to disable.

**Rules for this step:**
1. Explicit links (wiki-links, frontmatter) are always better than inferred ones
2. Every inferred edge type has a **kill switch** (config flag to disable)
3. Start with fewer, higher-quality edges — can always loosen thresholds later
4. If an edge type produces > 50% false positives in testing, raise threshold or cut it
5. Pruning is more important than adding — noisy graph is worse than sparse graph

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| **Keyword-similarity edges** | Jaccard overlap on keywords → `similar_to` edges |
| **Temporal edges** | Same-day notes get weak `temporal` edges |
| **Edge pruning** | Overloaded tags (30+ notes) downweighted to 0.05 |
| **Rebuild pipeline** | All passes integrated in correct order |

---

## Dependencies

No new packages. Builds on entity extraction from step 14a.

---

## Files to Modify

```
backend/
├── services/
│   └── graph_service.py           # MODIFY — similarity, temporal, pruning, pipeline order
├── tests/
│   └── test_graph_edge_quality.py # NEW — similarity, temporal, pruning tests
```

---

## A. Keyword-Similarity Edges

During graph rebuild, compute lightweight text similarity between notes.
No embeddings, no API calls — pure keyword overlap (Jaccard).

```python
def _compute_similarity_edges(graph: Graph, memory_path: Path) -> list[Edge]:
    """Compare notes by title + first 200 chars. Add similar_to edges for high overlap."""
    from services.context_builder import _extract_keywords

    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]
    if len(note_nodes) > 500:
        return []  # Skip for very large vaults to avoid O(n²)

    note_keywords: dict[str, set[str]] = {}
    for node in note_nodes:
        path = node.id[5:]  # strip "note:"
        filepath = memory_path / path
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8", errors="replace")
        _, body = parse_frontmatter(content)
        text = f"{node.label} {body[:200]}"
        keywords = _extract_keywords(text)
        if len(keywords) >= 3:
            note_keywords[node.id] = keywords

    new_edges = []
    node_ids = list(note_keywords.keys())
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            a, b = node_ids[i], node_ids[j]
            overlap = note_keywords[a] & note_keywords[b]
            union = note_keywords[a] | note_keywords[b]
            if len(union) == 0:
                continue
            jaccard = len(overlap) / len(union)
            if jaccard >= 0.25 and len(overlap) >= 4:
                weight = round(0.3 + jaccard * 0.4, 3)
                new_edges.append(Edge(
                    source=a, target=b, type="similar_to", weight=weight,
                ))

    return new_edges
```

**Thresholds (conservative start — can loosen later):**
- Jaccard ≥ 0.30 AND overlap ≥ 5 keywords → create edge
  *(Start stricter than intuition suggests. 0.25/4 produced too many weak edges in testing.)*
- Skip if vault > 500 notes (performance guard)
- Max 3 similarity edges per note (keep highest scoring)
- **Kill switch**: `SIMILARITY_EDGES_ENABLED = True` in config — can disable entirely

---

## B. Temporal Edges

Notes created on the same day get a weak `temporal` edge.

```python
def _compute_temporal_edges(graph: Graph, memory_path: Path) -> list[Edge]:
    """Group notes by creation date and add temporal edges within same day."""
    date_groups: dict[str, list[str]] = {}

    for node in graph.nodes.values():
        if node.type != "note":
            continue
        path = node.id[5:]
        filepath = memory_path / path
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8", errors="replace")
        fm, _ = parse_frontmatter(content)
        created = fm.get("created_at", "")
        if isinstance(created, str) and len(created) >= 10:
            day = created[:10]
            date_groups.setdefault(day, []).append(node.id)

    edges = []
    for day, node_ids in date_groups.items():
        if len(node_ids) < 2 or len(node_ids) > 10:
            continue  # Skip noise (too many) or singletons
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                edges.append(Edge(
                    source=node_ids[i], target=node_ids[j],
                    type="temporal", weight=0.15,
                ))

    return edges
```

**Temporal edges are the weakest signal.** Weight 0.15 (not 0.2) — same-day is
correlation, not causation. These should never dominate retrieval.
**Kill switch**: `TEMPORAL_EDGES_ENABLED = True` in config.

---

## C. Edge Pruning for Overloaded Tags

Tags connected to 30+ notes add noise. Downweight instead of deleting.

```python
def _prune_overloaded_tags(graph: Graph, max_degree: int = 30) -> None:
    """Downweight edges from tags that connect to too many notes."""
    tag_degree: dict[str, int] = {}
    for edge in graph.edges:
        if edge.type == "tagged":
            tag_id = edge.target if edge.target.startswith("tag:") else edge.source
            tag_degree[tag_id] = tag_degree.get(tag_id, 0) + 1

    overloaded = {tid for tid, deg in tag_degree.items() if deg > max_degree}
    if not overloaded:
        return

    pruned_edges = []
    for edge in graph.edges:
        if edge.type == "tagged" and (edge.source in overloaded or edge.target in overloaded):
            pruned_edges.append(Edge(
                source=edge.source, target=edge.target,
                type=edge.type, weight=0.05,
            ))
        else:
            pruned_edges.append(edge)

    graph.edges = pruned_edges
```

---

## D. Full Rebuild Pipeline Order

Updated `rebuild_graph` integrates all edge types in correct order:

```python
def rebuild_graph(workspace_path=None) -> Graph:
    graph = Graph()
    mem = _memory_path(workspace_path)

    # Pass 1: Parse notes, extract frontmatter edges (existing)
    for md_file in sorted(mem.rglob("*.md")):
        _process_note(graph, md_file, mem)

    # Pass 2: Entity extraction (from step 14a)
    _enrich_with_entities(graph, mem)

    # Pass 3: Bidirectional wiki-link resolution (from step 14a)
    _resolve_bidirectional_links(graph)

    # Pass 4: Keyword similarity edges (NEW)
    sim_edges = _compute_similarity_edges(graph, mem)
    for edge in sim_edges:
        graph.edges.append(edge)

    # Pass 5: Temporal edges (NEW)
    temp_edges = _compute_temporal_edges(graph, mem)
    for edge in temp_edges:
        graph.edges.append(edge)

    # Pass 6: Compute tag IDF and assign edge weights (existing)
    idf = compute_tag_idf(graph)
    _apply_tag_idf_weights(graph, idf)

    # Pass 7: Prune overloaded tags (NEW)
    _prune_overloaded_tags(graph)

    # Pass 8: Deduplicate edges
    graph.edges = list(set(graph.edges))

    _save_and_cache(graph, workspace_path)
    return graph
```

---

## Tests

```
test_similarity_edges_high_overlap    — two notes about same topic → similar_to edge
test_similarity_edges_low_overlap     — unrelated notes → no edge
test_similarity_edges_max_per_note    — max 3 similarity edges per note
test_similarity_edges_large_vault     — >500 notes → skipped gracefully

test_temporal_edges_same_day          — two notes same day → temporal edge
test_temporal_edges_different_days    — different days → no edge
test_temporal_edges_busy_day_skip     — >10 notes same day → skipped

test_prune_overloaded_tag_30plus      — tag with 31 notes → weight set to 0.05
test_prune_keeps_specific_tags        — tag with 5 notes → unchanged

test_rebuild_pipeline_order           — full rebuild produces all edge types
test_rebuild_idempotent               — rebuild twice gives same result
```

---

## Definition of Done

- [ ] Keyword-similarity edges created during rebuild (Jaccard ≥ 0.30, ≥ 5 overlapping keywords)
- [ ] Max 3 similarity edges per note (highest scoring)
- [ ] Skips similarity for vaults > 500 notes
- [ ] Temporal edges link notes from the same day (weight 0.15)
- [ ] Overloaded tags (30+ notes) have edges downweighted to 0.05
- [ ] Rebuild pipeline runs all 8 passes in correct order
- [ ] Performance: rebuild for 500 notes completes in < 5 seconds
- [ ] Kill switches work: each edge type can be disabled via config flag
- [ ] Quality check: manual review of 20 random inferred edges shows < 30% false positives
- [ ] All tests pass (10 test cases)
- [ ] Documentation updated
