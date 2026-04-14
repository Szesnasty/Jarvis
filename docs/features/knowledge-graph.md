---
title: Knowledge Graph
status: active
type: feature
sources:
  - backend/routers/graph.py
  - backend/services/graph_service.py
  - backend/services/entity_extraction.py
  - frontend/app/pages/graph.vue
  - frontend/app/components/GraphCanvas.vue
  - frontend/app/components/GraphNodePreview.vue
  - frontend/app/components/GraphFilterBar.vue
  - frontend/app/composables/useGraph.ts
depends_on: [memory]
last_reviewed: 2026-04-15
last_updated: 2026-04-15
---

# Knowledge Graph

## Summary

The knowledge graph is a derived, file-system-based relationship layer that links notes, tags, people, and folders into a navigable network. It is built entirely from Markdown files in `memory/` — no graph DB is involved — and can be fully regenerated at any time. The graph exists to surface connections across the user's notes that would otherwise require searching multiple files manually.

The graph supports weighted edges (IDF-scaled tag weights, type-based base weights), automatic entity extraction from note bodies, bidirectional wiki-link resolution, keyword-similarity edges between notes, temporal edges between same-day notes, and overloaded-tag pruning. The frontend provides interactive filtering by node type and time range, a rich node detail panel, and orphan detection.

## How It Works

### Building the graph

The graph is constructed by `rebuild_graph()` which scans every `.md` file under the workspace `memory/` directory in a 7-pass pipeline:

**Pass 1 — Parse notes and extract frontmatter edges.**
For each file, the service:
1. Parses frontmatter to extract `title`, `tags`, `people`, and `related` fields.
2. Scans the note body for Obsidian-style wiki links (`[[Note Name]]`) using a regex.
3. Creates nodes for the note itself, each referenced tag, each person, and the containing folder (`area`).
4. Creates edges between the note and whatever it references, typed by relationship (`tagged`, `linked`, `mentions`, `related`, `part_of`).

**Pass 2 — Entity extraction.**
`_enrich_with_entities()` reads each note's body text and runs regex-based entity extraction (`entity_extraction.py`) to discover person names not listed in frontmatter. Extracted person names with confidence ≥ 0.5 are added as `person:` nodes with `mentions` edges. Confidence is boosted for names that already exist in the graph.

**Pass 3 — Bidirectional wiki-link resolution.**
`_resolve_bidirectional_links()` ensures that for every `linked` edge A→B, a reverse edge B→A is also present (with reduced weight 0.6).

**Pass 4 — Keyword similarity edges.**
`_compute_similarity_edges()` compares notes by title + first 200 characters. For each pair with Jaccard keyword overlap ≥ 0.25 and at least 4 shared keywords, a `similar_to` edge is added. Each note is capped at 3 similarity edges. Skipped entirely for workspaces with >500 notes.

**Pass 5 — Temporal edges.**
`_compute_temporal_edges()` groups notes by `created_at` or `date` frontmatter field. Notes created on the same day receive `temporal` edges (weight 0.2). Day groups with >10 notes are skipped.

**Pass 6 — IDF-weighted edge weights.**
`_apply_edge_weights()` assigns weights to all edges. Each edge type has a base weight defined in `_EDGE_BASE_WEIGHT`:

| Edge type   | Base weight |
|-------------|-------------|
| `linked`    | 1.0         |
| `related`   | 0.9         |
| `mentions`  | 0.8         |
| `tagged`    | 0.6         |
| `similar_to`| 0.5         |
| `part_of`   | 0.3         |
| `temporal`  | 0.2         |

For `tagged` edges, the base weight is multiplied by the tag's IDF score (normalized 0–1). Tags appearing on many notes get lower weight; rare tags get higher weight.

**Pass 7 — Overloaded tag pruning.**
`_prune_overloaded_tags()` downweights tags connected to >30 notes to a weight of 0.05, suppressing noise from overly common tags.

Node identity is namespaced by type: `note:daily/2026-04-14.md`, `tag:health`, `person:Alice`, `area:projects`. This prevents collisions across different entity types that share a name.

The completed graph is serialised to `{workspace}/graph/graph.json` and held in a module-level in-process cache (`_graph_cache`). Subsequent requests within the same server lifetime hit the cache directly; no disk I/O occurs until `invalidate_cache()` is called.

### Entity extraction

`entity_extraction.py` provides regex-based extraction of person names, dates, and projects from note body text. Person names are detected in two ways:
- **Standalone**: capitalized multi-word names (`Alice Johnson`), filtered against a skiplist of common false positives (days, months, acronyms).
- **Contextual**: names preceded by signal words (`with`, `from`, `by`, `met`, `called`, etc.), getting higher confidence.

Confidence is boosted if the name already exists in the graph's person nodes. Results are deduplicated by `(text.lower(), type)`, keeping the highest-confidence match.

### Node detail

`get_node_detail()` aggregates rich information for a single node: the node itself, a 200-character body preview (for notes), lists of connected notes/tags/people, neighbor count, and degree. This powers the frontend's side panel.

### Orphan detection

`find_orphans()` returns note nodes with degree 0 (no edges at all). These are surfaced in the frontend's orphan banner.

### Neighbor traversal

`get_neighbors` performs a BFS expansion to a configurable depth, walking edges in both directions (the graph is effectively undirected for traversal). `query_entity` wraps this with a fuzzy label/ID match so callers can ask "what is connected to Alice?" without knowing the exact node ID.

### Rebuild flow

The `/api/graph/rebuild` endpoint clears the cache and triggers a full re-scan of the `memory/` directory. The graph page calls `loadGraph()` on mount to fetch the already-built graph without triggering a rescan. A `Rebuild` button in the toolbar triggers `rebuildGraph()` when the user explicitly requests a full rescan.

`rebuild_graph` is now wrapped in `asyncio.to_thread` at all async call sites: the `/api/graph/rebuild` endpoint in `graph.py` and `session_service.save_conversation`. This means the synchronous file scan runs in a thread pool worker and no longer blocks the event loop.

### Manual edge creation

`POST /api/graph/edges` allows creating `related` or `linked` edges between two note nodes. The endpoint updates the source note's frontmatter `related` list and triggers a full graph rebuild.

### Visualisation

The frontend renders the graph using `force-graph` (a D3-force-backed Canvas library loaded via dynamic import). Node size scales with connection degree. Edge appearance is type-specific: `linked`/`related` edges carry directional arrows; `part_of` edges use a dashed line; `tagged` and `linked` edges emit animated particles; `similar_to` edges are gray dashed lines; `temporal` edges are yellow dotted lines. Area nodes use a stronger repulsive force to push themselves to the periphery of the layout.

Labels are shown selectively: always for `area` nodes, always for nodes with 4+ connections, and for any hovered or highlighted node. At zoom levels above 1.2 all labels appear. Labels longer than 25 characters are truncated with an ellipsis unless the node is hovered.

The `GraphCanvas` component destroys and recreates the entire `force-graph` instance whenever the node or edge data changes (`watch` on `[props.nodes, props.edges]`). This is a full teardown-and-rebuild rather than an incremental update. The `ResizeObserver` is now disconnected at the start of `buildGraph()` and re-attached to the new instance's container after the graph is built, preventing orphaned observer registrations on repeated data refreshes.

### Interactive filtering

The `GraphFilterBar` component provides:
- **Type toggles** — show/hide Notes, Tags, People, and Areas independently.
- **Time range** — filter to notes from last 7/30/90 days.
- **Orphan highlight** — toggle to show orphaned (unconnected) notes with badge count.
- **Search** — filter nodes by label substring match.

`useGraph` exposes `filteredNodes` and `filteredEdges` computed refs that apply all active filters. The graph page passes these filtered arrays (not the raw graph data) to `GraphCanvas`.

### Node detail panel

Clicking a node in the graph opens the `GraphNodePreview` side panel which loads rich detail via `GET /api/graph/nodes/{node_id}/detail`. The panel shows:
- Type badge and title
- Body preview (first 200 chars for note nodes)
- Degree and neighbor count stats
- Connected tags, people (as clickable chips), and notes
- "Ask about this" button (navigates to `/main?graph_scope={node_id}` for scoped chat)
- "Open in Memory" link (for note nodes)

## Key Files

- `backend/routers/graph.py` — REST endpoints: fetch full graph, stats, neighbors, node detail, orphans, create edge, trigger rebuild.
- `backend/services/graph_service.py` — All graph logic: `Node`/`Edge`/`Graph` dataclasses, 7-pass rebuild pipeline, IDF computation, entity enrichment, bidirectional links, similarity/temporal edges, tag pruning, node detail, orphan detection, BFS traversal, in-process cache, disk persistence.
- `backend/services/entity_extraction.py` — Regex-based entity extraction: person names (standalone + contextual), dates (ISO, natural language, relative), project names. Dedup with confidence ranking.
- `frontend/app/composables/useGraph.ts` — Reactive wrapper around the API; exposes `graph`, `stats`, `orphans`, `selectedNode`, `filteredNodes`, `filteredEdges`, `loadGraph`, `rebuildGraph`, `queryNeighbors`, `selectNode`, `setFilters`.
- `frontend/app/pages/graph.vue` — Graph page layout; filter bar, canvas, orphan banner, node detail side panel with navigate/ask-about/open-in-memory actions.
- `frontend/app/components/GraphCanvas.vue` — Canvas rendering via `force-graph`; custom node drawing (multi-layer glow), per-type edge styling (7 edge types with distinct colors/dashes), hover tooltips, drag/zoom/pan, and exposed `zoomIn`/`zoomOut`/`zoomToFit` methods.
- `frontend/app/components/GraphFilterBar.vue` — Filter toolbar: type toggles with colored dots, time range select, orphan toggle with count badge, label search input.
- `frontend/app/components/GraphNodePreview.vue` — Rich side panel for selected node: preview, stats, connected entities, action buttons.

## API / Interface

### REST endpoints

```
GET  /api/graph
```
Returns the full graph as nodes and edges arrays. Returns `{"nodes": [], "edges": []}` when no graph exists yet.

```
GET  /api/graph/stats
```
Returns aggregate counts and the top 5 highest-degree nodes.

```
GET  /api/graph/neighbors?node_id={id}&depth={n}
```
Returns neighbor nodes within `depth` hops of `node_id`. Depth defaults to 1, capped at 5. Returns `[]` when the graph is absent or the node is not found.

```
GET  /api/graph/nodes/{node_id}/detail
```
Returns rich detail for a single node: the node itself, a body preview (for notes), lists of connected notes/tags/people, neighbor count, and degree. Returns 404 if the node is not found.

```
GET  /api/graph/orphans
```
Returns note nodes with degree 0 (no edges). Each entry includes `id`, `label`, and `folder`.

```
POST /api/graph/edges
```
Creates a manual `related` or `linked` edge between two `note:` nodes. Updates the source note's frontmatter `related` list and triggers a graph rebuild. Returns 400 for invalid edge types or non-note nodes.

```
POST /api/graph/rebuild
```
Clears the in-process cache, rescans the entire `memory/` directory with the 7-pass pipeline, writes a new `graph.json`, and returns updated stats.

### Graph data format

```typescript
interface GraphNode {
  id: string       // namespaced: "note:path/to/file.md", "tag:health", "person:Alice", "area:projects"
  type: string     // "note" | "tag" | "person" | "area"
  label: string    // display name (frontmatter title or file stem for notes)
  folder: string   // relative folder path within memory/, empty for root-level notes
}

interface GraphEdge {
  source: string   // node id
  target: string   // node id
  type: string     // "tagged" | "linked" | "mentions" | "related" | "part_of" | "similar_to" | "temporal"
  weight: number   // 0.0–1.0, IDF-adjusted for tags, base weight for other types
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

interface GraphStats {
  node_count: number
  edge_count: number
  top_connected: { id: string; degree: number }[]
}

interface GraphNodeDetail {
  node: GraphNode
  preview: string | null         // first 200 chars of note body, null for non-note nodes
  connected_notes: GraphNode[]
  connected_tags: string[]
  connected_people: string[]
  neighbor_count: number
  degree: number
}

interface GraphOrphan {
  id: string
  label: string
  folder: string
}

interface GraphFilters {
  showNotes: boolean
  showTags: boolean
  showPeople: boolean
  showAreas: boolean
  timeRange: 'all' | '7d' | '30d' | '90d'
  showOrphans: boolean
  searchText: string
}
```

### `useGraph` composable

```typescript
function useGraph(): {
  graph: Ref<GraphData>
  stats: Ref<GraphStats>
  orphans: Ref<GraphOrphan[]>
  selectedNode: Ref<GraphNode | null>
  filteredNodes: ComputedRef<GraphNode[]>
  filteredEdges: ComputedRef<GraphEdge[]>
  highlightedNodeId: Ref<string>
  isLoading: Ref<boolean>
  loadGraph(): Promise<void>       // loads graph + stats + orphans without rebuild
  rebuildGraph(): Promise<void>    // triggers POST /rebuild then reloads
  queryNeighbors(nodeId: string, depth?: number): Promise<GraphNode[]>
  selectNode(node: GraphNode | null): void
  setFilters(f: GraphFilters): void
}
```

### `GraphCanvas` exposed methods

```typescript
defineExpose({
  zoomIn(): void
  zoomOut(): void
  zoomToFit(): void
})
```

## Gotchas

**Wiki link targets may not exist as nodes.** When `rebuild_graph` encounters a `[[Link]]` it unconditionally creates an edge to `note:Link.md`. If that file does not exist in `memory/`, the target node will be referenced by an edge but will not exist in `graph.nodes`. The `GraphCanvas` component filters out edges whose source or target is not in the visible node set, so dangling edges never render.

**The in-process cache is invalidated on destructive operations but not on every write.** Deleting a memory note (`memory_service.delete_note`) and deleting a session (`DELETE /api/sessions/{id}`) both call `invalidate_cache()` so the graph rebuilds from the current filesystem state on next access. However, creating or updating a memory note does not invalidate the cache automatically — those changes only appear after a `POST /api/graph/rebuild` or server restart. The graph page triggers a rebuild on every mount, which is the primary refresh mechanism for non-destructive changes.

**`rebuild_graph` is synchronous but wrapped in `asyncio.to_thread`.** It calls `Path.rglob()` and reads every `.md` file before returning. All async call sites (the `/api/graph/rebuild` endpoint, `POST /api/graph/edges`, and `session_service.save_conversation`) run it via `asyncio.to_thread` so the file scan executes in a thread pool worker rather than blocking the event loop. On very large workspaces it will still occupy a thread for the duration of the scan.

**Similarity edge computation is O(n²) and capped at 500 notes.** `_compute_similarity_edges` compares every pair of notes. For workspaces with >500 notes the entire pass is skipped to avoid latency. Each note is also capped at 3 similarity edges.

**Entity extraction is regex-based and English-centric.** The person-name regexes expect capitalized multi-word Latin names. They will miss names in non-Latin scripts and produce false positives for capitalized common phrases not in the skiplist.

**Edge weights are recalculated on every rebuild.** The `Edge` dataclass is frozen, so `_apply_edge_weights()` creates a new list of edges. This means manual weight adjustments would be lost on rebuild.

**`force-graph` is dynamically imported.** The `import('force-graph')` call inside `buildGraph` happens lazily on first render. If the module fails to load (e.g. network issue in dev mode), `buildGraph` will throw silently and the canvas will remain blank.

**Tooltip position is not updated from mouse events.** `tooltipStyle` is initialised to `{left: '0px', top: '0px'}` and never changed at runtime. The tooltip renders at the top-left corner of the canvas, not at the cursor. This is a known visual limitation.

**`rebuildGraph` in `useGraph` calls `apiRebuild` then `fetchGraph` separately.** The rebuild endpoint returns only stats, not the full graph, so a second request is required. These two requests are not atomic — a concurrent rebuild triggered from elsewhere could cause the stats and graph data to be inconsistent for the brief window between the two calls.
