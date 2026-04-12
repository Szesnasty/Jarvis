# Step 08 — Knowledge Graph

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 07 — Planning & Ops](step-07-planning-ops.md) | **Next**: [Step 09 — Specialists](step-09-specialists.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Build a lightweight knowledge graph from explicit relations in notes. Integrate it into retrieval. Provide a visual graph UI.

---

## Files to Create / Modify

### Backend
```
backend/
├── services/
│   ├── graph_service.py       # NEW — graph CRUD + queries
│   ├── retrieval.py           # NEW — hybrid retrieval with graph expansion
│   ├── context_builder.py     # MODIFY — use retrieval.py instead of raw search
│   └── tools.py               # MODIFY — add query_graph tool
├── routers/
│   └── graph.py               # NEW — graph endpoints
└── models/
    └── schemas.py             # MODIFY — add graph schemas
```

### Frontend
```
frontend/src/
├── views/
│   └── GraphView.vue          # NEW — interactive graph visualization
├── components/
│   └── GraphCanvas.vue        # NEW — D3/vis-network graph renderer
├── router/
│   └── index.ts               # MODIFY — add /graph route
├── services/
│   └── api.ts                 # MODIFY — add graph API calls
└── types/
    └── index.ts               # MODIFY — add graph types
```

---

## Specification

### Graph Data Model

The graph is stored as `Jarvis/graph/graph.json`:

```json
{
  "nodes": [
    {
      "id": "note:projects/jarvis.md",
      "type": "note",
      "label": "Jarvis Project",
      "folder": "projects"
    },
    {
      "id": "tag:ai",
      "type": "tag",
      "label": "ai"
    },
    {
      "id": "person:michał",
      "type": "person",
      "label": "Michał"
    }
  ],
  "edges": [
    {
      "source": "note:projects/jarvis.md",
      "target": "tag:ai",
      "type": "tagged"
    },
    {
      "source": "note:projects/jarvis.md",
      "target": "person:michał",
      "type": "mentions"
    },
    {
      "source": "note:projects/jarvis.md",
      "target": "note:daily/2026-04-10.md",
      "type": "linked"
    }
  ],
  "updated_at": "2026-04-12T10:00:00"
}
```

Node types: `note`, `tag`, `person`, `project`, `area`, `topic`
Edge types: `tagged`, `linked`, `mentions`, `related`, `part_of`, `source_for`

### Graph Building (Explicit Relations Only)

**MVP scope: no AI inference.** Graph is built from explicit signals:

1. **Folder structure** → `part_of` edges (note belongs to folder/area)
2. **Wiki links** `[[other-note]]` → `linked` edges
3. **Frontmatter tags** → `tagged` edges to tag nodes
4. **Frontmatter fields**: `related`, `project`, `person` → corresponding edges
5. **Specialist source bindings** (step 09) → `source_for` edges

```python
# graph_service.py
async def rebuild_graph(memory_path: Path) -> Graph:
    """Full rebuild from Markdown files. No AI calls."""
    graph = Graph()
    for md_file in memory_path.rglob("*.md"):
        frontmatter, body = parse_frontmatter(md_file.read_text())
        note_id = f"note:{md_file.relative_to(memory_path)}"
        graph.add_node(note_id, type="note", label=frontmatter.get("title", md_file.stem))

        # Tags
        for tag in frontmatter.get("tags", []):
            graph.add_node(f"tag:{tag}", type="tag", label=tag)
            graph.add_edge(note_id, f"tag:{tag}", type="tagged")

        # Wiki links
        for link in extract_wiki_links(body):
            graph.add_edge(note_id, f"note:{link}", type="linked")

        # Frontmatter relations
        for person in frontmatter.get("people", []):
            graph.add_node(f"person:{person}", type="person", label=person)
            graph.add_edge(note_id, f"person:{person}", type="mentions")

    return graph
```

### Graph Service API

#### `GET /api/graph`

Returns full graph JSON (for visualization).

#### `GET /api/graph/neighbors?node_id=note:projects/jarvis.md&depth=1`

Returns subgraph: node + its neighbors up to N hops.

#### `POST /api/graph/rebuild`

Triggers full graph rebuild from disk. Returns new graph stats.

#### `GET /api/graph/stats`

Returns: node count, edge count, most connected nodes.

### `query_graph` Tool

```python
{
    "name": "query_graph",
    "description": "Query the knowledge graph to find related notes, people, tags, or topics. Use to discover connections the user may not remember.",
    "input_schema": {
        "type": "object",
        "properties": {
            "entity": {"type": "string", "description": "Entity to search for (note title, person, tag, topic)"},
            "relation_type": {"type": "string", "description": "Optional: filter by relation type"},
            "depth": {"type": "integer", "description": "How many hops to traverse", "default": 1}
        },
        "required": ["entity"]
    }
}
```

Returns: list of related nodes with their relation types and paths.

### Hybrid Retrieval (`services/retrieval.py`)

Replace direct search in context_builder with a pipeline:

```python
async def retrieve(query: str, limit: int = 5) -> list[RetrievalResult]:
    """Hybrid retrieval: structural search → graph expansion → rank."""

    # 1. Structural search (SQLite FTS)
    search_results = await memory_service.search_notes(query, limit=limit * 2)

    # 2. Graph expansion
    expanded = set()
    for result in search_results[:3]:
        neighbors = graph_service.get_neighbors(f"note:{result.path}", depth=1)
        expanded.update(neighbors)

    # 3. Merge + deduplicate
    all_candidates = merge_results(search_results, expanded)

    # 4. Rank by relevance (simple scoring: exact match > tag match > neighbor)
    ranked = rank_results(all_candidates, query)

    # 5. Trim to limit
    return ranked[:limit]
```

Update `context_builder.py` to use `retrieval.retrieve()` instead of direct `memory_service.search_notes()`.

---

### Frontend

#### `GraphView.vue`

- Full-page graph visualization
- Uses D3.js force-directed layout or vis-network
- Node colors by type (notes: blue, tags: green, people: orange, etc.)
- Click node → show note preview sidebar
- Search bar to find and focus on a node
- Zoom, pan, drag nodes

#### `GraphCanvas.vue`

- Handles D3/vis-network rendering
- Props: `nodes`, `edges`, `highlightedNode`
- Emits: `nodeClick`, `nodeHover`
- Responsive: fills parent container

---

## Key Decisions

- **MVP graph: explicit relations only** — no AI-inferred relations
- Graph stored as single JSON file — simple, portable, rebuildable
- `rebuild_graph()` reads all .md files — runs in seconds for < 1000 notes
- Graph rebuild triggered: on workspace init, on demand, on note create/update (incremental later)
- D3 force layout for visualization — well-supported, customizable, no extra deps
- Graph is a **derived layer** — if deleted, `rebuild` restores it from Markdown files

---

## Acceptance Criteria

- [ ] `POST /api/graph/rebuild` builds graph from existing notes
- [ ] Graph reflects: folder membership, tags, wiki links, frontmatter relations
- [ ] `query_graph` tool returns related notes when Claude uses it
- [ ] Retrieval pipeline uses graph expansion (neighbors of search results)
- [ ] Graph view shows interactive visualization with colored nodes
- [ ] Click node in graph → see note preview
- [ ] Deleting `graph.json` and rebuilding restores the full graph
- [ ] No AI API calls made during graph building

---

## Tests

### Backend — `tests/test_graph_service.py` (~18 tests)
- `test_build_graph_empty` → 0 nodes, 0 edges when no notes
- `test_build_graph_single_note` → 1 node, 0 edges
- `test_build_graph_multiple_notes` → N nodes for N notes
- `test_graph_folder_membership_edge` → note → folder edge exists
- `test_graph_shared_tag_edge` → two notes with same tag → edge between them
- `test_graph_no_edge_different_tags` → different tags → no edge
- `test_graph_wikilink_edge` → `[[note-b]]` in note-a → edge a→b
- `test_graph_wikilink_bidirectional` → backlink also traversable
- `test_graph_frontmatter_related` → `related: [note-b]` → edge
- `test_graph_node_has_metadata` → node has id, title, folder, tags
- `test_graph_edge_has_type` → edge has type (tag, folder, link, related)
- `test_query_neighbors` → returns 1-hop neighbors of node
- `test_query_neighbors_depth_2` → returns 2-hop neighbors
- `test_query_neighbors_empty` → isolated node returns `[]`
- `test_graph_rebuild_idempotent` → build twice = same graph
- `test_graph_rebuild_after_delete` → delete graph.json → rebuild = same result
- `test_graph_update_incremental` → adding note updates graph without full rebuild
- `test_no_anthropic_calls` → mock Anthropic client, assert 0 calls

### Backend — `tests/test_graph_retrieval.py` (~8 tests)
- `test_retrieval_search_only` → FTS5 results without graph expansion
- `test_retrieval_with_graph_expansion` → FTS5 + neighbors included
- `test_retrieval_deduplication` → same note from search + graph appears once
- `test_retrieval_ranking` → direct match ranked above graph neighbor
- `test_retrieval_max_results` → respects limit parameter
- `test_retrieval_empty_query` → returns `[]`
- `test_retrieval_no_graph` → works even if graph.json missing (fallback to search-only)
- `test_retrieval_via_tool` → Claude `query_knowledge` tool uses retrieval pipeline

### Backend — `tests/test_graph_api.py` (~8 tests)
- `test_post_rebuild_200` → 200 + `{nodes: N, edges: M}`
- `test_get_graph_200` → 200 + full graph JSON
- `test_get_graph_empty` → 200 + empty graph structure
- `test_get_graph_query_200` → 200 + filtered neighbors
- `test_get_graph_query_unknown_node` → 200 + `[]`
- `test_get_graph_stats` → 200 + node/edge/component counts
- `test_graph_not_built_yet` → 404 or empty graph
- `test_rebuild_after_note_change` → graph reflects updated note

### Frontend — `tests/pages/graph.test.ts` (~8 tests)
- Renders visualization container (SVG or canvas)
- Nodes count matches API response
- Clicking node emits `select` event with node id
- Selected node shows preview panel
- Preview panel shows note title + excerpt
- Zoom controls work (zoom in, zoom out, fit)
- Node colors differ by type/folder
- Empty state shows "No graph — create notes first"

### Frontend — `tests/composables/useGraph.test.ts` (~5 tests)
- `loadGraph()` fetches from API
- `rebuildGraph()` calls POST rebuild
- `selectedNode` reactive ref updates on click
- `queryNeighbors(nodeId)` returns filtered data
- Loading state during fetch

### Regression suite
```bash
cd backend && python -m pytest tests/ -v
cd frontend && npx vitest run
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~172 backend tests
cd frontend && npx vitest run                      # ~124 frontend tests
```

**Expected total: ~296 tests**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all ~172 backend tests pass (including regression)
- [ ] `npx vitest run` — all ~124 frontend tests pass (including regression)
- [ ] Source-of-truth verified: delete graph.json → rebuild → same graph
- [ ] No AI API calls during graph operations (verified by mock test)
- [ ] Committed with message `feat: step-08 knowledge graph`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
