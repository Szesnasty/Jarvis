---
title: Knowledge Graph
status: active
type: feature
sources:
  - backend/routers/graph.py
  - backend/services/graph_service.py
  - frontend/app/pages/graph.vue
  - frontend/app/components/GraphCanvas.vue
  - frontend/app/composables/useGraph.ts
depends_on: [memory]
last_reviewed: 2026-04-14
last_updated: 2026-04-14
---

# Knowledge Graph

## Summary

The knowledge graph is a derived, file-system-based relationship layer that links notes, tags, people, and folders into a navigable network. It is built entirely from Markdown files in `memory/` — no graph DB is involved — and can be fully regenerated at any time. The graph exists to surface connections across the user's notes that would otherwise require searching multiple files manually.

## How It Works

### Building the graph

The graph is constructed by scanning every `.md` file under the workspace `memory/` directory. For each file the service does four things:

1. **Parses frontmatter** to extract `title`, `tags`, `people`, and `related` fields.
2. **Scans the note body** for Obsidian-style wiki links (`[[Note Name]]`) using a regex.
3. **Creates nodes** for the note itself, each referenced tag, each person, and the containing folder (`area`).
4. **Creates edges** between the note and whatever it references, typed by relationship (`tagged`, `linked`, `mentions`, `related`, `part_of`).

Node identity is namespaced by type: `note:daily/2026-04-14.md`, `tag:health`, `person:Alice`, `area:projects`. This prevents collisions across different entity types that share a name.

The completed graph is serialised to `{workspace}/graph/graph.json` and held in a module-level in-process cache (`_graph_cache`). Subsequent requests within the same server lifetime hit the cache directly; no disk I/O occurs until `invalidate_cache()` is called.

### Neighbor traversal

`get_neighbors` performs a BFS expansion to a configurable depth, walking edges in both directions (the graph is effectively undirected for traversal). `query_entity` wraps this with a fuzzy label/ID match so callers can ask "what is connected to Alice?" without knowing the exact node ID.

### Rebuild flow

The `/api/graph/rebuild` endpoint clears the cache and triggers a full re-scan of the `memory/` directory. The graph page calls `loadGraph()` on mount to fetch the already-built graph without triggering a rescan. A `Rebuild` button in the toolbar triggers `rebuildGraph()` when the user explicitly requests a full rescan.

`rebuild_graph` is now wrapped in `asyncio.to_thread` at all async call sites: the `/api/graph/rebuild` endpoint in `graph.py` and `session_service.save_conversation`. This means the synchronous file scan runs in a thread pool worker and no longer blocks the event loop.

### Visualisation

The frontend renders the graph using `force-graph` (a D3-force-backed Canvas library loaded via dynamic import). Node size scales with connection degree. Edge appearance is type-specific: `linked`/`related` edges carry directional arrows; `part_of` edges use a dashed line; `tagged` and `linked` edges emit animated particles. Area nodes use a stronger repulsive force to push themselves to the periphery of the layout.

Labels are shown selectively: always for `area` nodes, always for nodes with 4+ connections, and for any hovered or highlighted node. At zoom levels above 1.2 all labels appear. Labels longer than 25 characters are truncated with an ellipsis unless the node is hovered.

The `GraphCanvas` component destroys and recreates the entire `force-graph` instance whenever the node or edge data changes (`watch` on `[props.nodes, props.edges]`). This is a full teardown-and-rebuild rather than an incremental update. The `ResizeObserver` is now disconnected at the start of `buildGraph()` and re-attached to the new instance's container after the graph is built, preventing orphaned observer registrations on repeated data refreshes.

## Key Files

- `backend/routers/graph.py` — Four REST endpoints: fetch full graph, fetch stats, fetch neighbors for a node, trigger rebuild.
- `backend/services/graph_service.py` — All graph logic: `Node`/`Edge`/`Graph` dataclasses, wiki-link extraction, rebuild pipeline, BFS traversal, in-process cache, disk persistence.
- `frontend/app/composables/useGraph.ts` — Thin reactive wrapper around the API; exposes `graph`, `stats`, `selectedNode`, `loadGraph`, `rebuildGraph`, `queryNeighbors`, `selectNode`.
- `frontend/app/pages/graph.vue` — Graph page layout; toolbar with Rebuild/Zoom controls, node count stats, and a side panel showing selected node details.
- `frontend/app/components/GraphCanvas.vue` — Canvas rendering via `force-graph`; custom node drawing (multi-layer glow), per-type edge styling, hover tooltips, drag/zoom/pan, and exposed `zoomIn`/`zoomOut`/`zoomToFit` methods.

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
Returns neighbor nodes within `depth` hops of `node_id`. Depth defaults to 1. Returns `[]` when the graph is absent or the node is not found.

```
POST /api/graph/rebuild
```
Clears the in-process cache, rescans the entire `memory/` directory, writes a new `graph.json`, and returns updated stats.

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
  type: string     // "tagged" | "linked" | "mentions" | "related" | "part_of"
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
```

### `useGraph` composable

```typescript
function useGraph(): {
  graph: Ref<GraphData>
  stats: Ref<GraphStats>
  selectedNode: Ref<GraphNode | null>
  isLoading: Ref<boolean>
  loadGraph(): Promise<void>       // loads existing graph without rebuild
  rebuildGraph(): Promise<void>    // triggers POST /rebuild then reloads
  queryNeighbors(nodeId: string, depth?: number): Promise<GraphNode[]>
  selectNode(node: GraphNode | null): void
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

**Wiki link targets may not exist as nodes.** When `rebuild_graph` encounters a `[[Link]]` it unconditionally creates an edge to `note:Link.md`. If that file does not exist in `memory/`, the target node will be referenced by an edge but will not exist in `graph.nodes`. The graph data structure allows dangling edges, so the visualiser must tolerate them — `force-graph` does, but any code doing `graph.nodes[targetId]` lookups should guard for `undefined`.

**The in-process cache is invalidated on destructive operations but not on every write.** Deleting a memory note (`memory_service.delete_note`) and deleting a session (`DELETE /api/sessions/{id}`) both call `invalidate_cache()` so the graph rebuilds from the current filesystem state on next access. However, creating or updating a memory note does not invalidate the cache automatically — those changes only appear after a `POST /api/graph/rebuild` or server restart. The graph page triggers a rebuild on every mount, which is the primary refresh mechanism for non-destructive changes.

**`rebuild_graph` is synchronous but wrapped in `asyncio.to_thread`.** It calls `Path.rglob()` and reads every `.md` file before returning. All async call sites (the `/api/graph/rebuild` endpoint and `session_service.save_conversation`) run it via `asyncio.to_thread` so the file scan executes in a thread pool worker rather than blocking the event loop. On very large workspaces it will still occupy a thread for the duration of the scan.

**`force-graph` is dynamically imported.** The `import('force-graph')` call inside `buildGraph` happens lazily on first render. If the module fails to load (e.g. network issue in dev mode), `buildGraph` will throw silently and the canvas will remain blank.

**Tooltip position is not updated from mouse events.** `tooltipStyle` is initialised to `{left: '0px', top: '0px'}` and never changed at runtime. The tooltip renders at the top-left corner of the canvas, not at the cursor. This is a known visual limitation.

**`rebuildGraph` in `useGraph` calls `apiRebuild` then `fetchGraph` separately.** The rebuild endpoint returns only stats, not the full graph, so a second request is required. These two requests are not atomic — a concurrent rebuild triggered from elsewhere could cause the stats and graph data to be inconsistent for the brief window between the two calls.
