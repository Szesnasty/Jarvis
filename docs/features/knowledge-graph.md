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

The `/api/graph/rebuild` endpoint clears the cache and triggers a full re-scan of the `memory/` directory. The graph page calls `rebuildGraph()` automatically on every mount, so visiting the graph view always triggers a full rescan rather than loading the cached graph. A `Rebuild` button in the toolbar allows the user to trigger another rescan manually.

`rebuild_graph` is also called inline — without offloading to a thread — from `session_service.py` after a conversation is saved to memory, and from `ingest.py` and `url_ingest.py` after files are ingested. All of these call sites are inside async functions, meaning the synchronous file scan blocks the event loop until it completes.

### Visualisation

The frontend renders the graph using `force-graph` (a D3-force-backed Canvas library loaded via dynamic import). Node size scales with connection degree. Edge appearance is type-specific: `linked`/`related` edges carry directional arrows; `part_of` edges use a dashed line; `tagged` and `linked` edges emit animated particles. Area nodes use a stronger repulsive force to push themselves to the periphery of the layout.

Labels are shown selectively: always for `area` nodes, always for nodes with 4+ connections, and for any hovered or highlighted node. At zoom levels above 1.2 all labels appear. Labels longer than 25 characters are truncated with an ellipsis unless the node is hovered.

The `GraphCanvas` component destroys and recreates the entire `force-graph` instance whenever the node or edge data changes (`watch` on `[props.nodes, props.edges]`). This is a full teardown-and-rebuild rather than an incremental update. A `ResizeObserver` is attached once on mount and kept alive; however, when `buildGraph` is called again due to data changes, a new `force-graph` instance is created without re-attaching or replacing the existing `ResizeObserver`, leaving the old observer orphaned. The observer is only cleaned up in `onBeforeUnmount`.

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

**The in-process cache is never automatically invalidated.** Writing or deleting a memory file does not update the graph until either the server restarts or a `POST /api/graph/rebuild` is issued. The graph page triggers a rebuild on every mount, which is the primary refresh mechanism. Background writes (e.g. saving a chat result to memory) do not update the graph automatically.

**`rebuild_graph` is synchronous and blocks the event loop.** It calls `Path.rglob()` and reads every `.md` file before returning. It is called directly (without `asyncio.to_thread`) from three async contexts: the `/api/graph/rebuild` endpoint, `session_service.save_conversation`, and the ingest pipeline. On large workspaces this will stall all concurrent requests. Acceptable for MVP but needs to move to a background task or async file I/O if memory grows large.

**`force-graph` is dynamically imported.** The `import('force-graph')` call inside `buildGraph` happens lazily on first render. If the module fails to load (e.g. network issue in dev mode), `buildGraph` will throw silently and the canvas will remain blank.

**Tooltip position is not updated from mouse events.** `tooltipStyle` is initialised to `{left: '0px', top: '0px'}` and never changed at runtime. The tooltip renders at the top-left corner of the canvas, not at the cursor. This is a known visual limitation.

**`rebuildGraph` in `useGraph` calls `apiRebuild` then `fetchGraph` separately.** The rebuild endpoint returns only stats, not the full graph, so a second request is required. These two requests are not atomic — a concurrent rebuild triggered from elsewhere could cause the stats and graph data to be inconsistent for the brief window between the two calls.

## Known Issues

### High severity

**Duplicate edges accumulate on every rebuild** (`graph_service.py:36`). `Graph.add_edge` always appends to `self.edges` without checking whether the same `(source, target, type)` triple already exists. Because `rebuild_graph` creates a fresh `Graph()` instance each time this does not cause accumulation across rebuilds in isolation — but `load_graph` also calls `add_edge` for every edge in the persisted JSON, and if `graph.json` was written with duplicates (e.g. from two rapid rebuilds before a cache hit) those duplicates are loaded faithfully. More importantly, the `Graph` dataclass has no dedup invariant, so any future code path that adds edges to an existing instance will silently accumulate duplicates. The `stats()` method counts edges naively, so duplicate edges inflate degree counts and the top-connected list.

**`rebuild_graph` called synchronously inside async handler** (`session_service.py:349`, via `graph_service.py`). After `save_conversation` writes a conversation note to disk it calls `graph_service.rebuild_graph(...)` directly — a fully synchronous, blocking function — from inside an `async def`. This occupies the event loop for as long as the full memory scan takes. The call is wrapped in a bare `try/except` that swallows all exceptions, so failures are silent. Fix: wrap with `await asyncio.to_thread(graph_service.rebuild_graph, ...)` or move to a background task.

### Medium severity

**Unbounded `depth` parameter on `/api/graph/neighbors`** (`graph.py:25`). The endpoint accepts `depth: int = 1` with no upper bound. A caller passing `depth=999` on a graph with many interconnected nodes will trigger a BFS that walks the entire graph repeatedly. There is no rate limit, authentication, or cap. Fix: clamp depth server-side, e.g. `depth = min(depth, 5)`.

**`rebuildGraph()` called on every mount instead of `loadGraph()`** (`graph.vue:63`). `onMounted` calls `rebuildGraph()`, which issues a `POST /api/graph/rebuild` followed by a `GET /api/graph`. Every navigation to the graph page rescans all memory files from disk regardless of whether anything changed since the last visit. `loadGraph()` exists specifically to fetch the already-built graph without triggering a rescan, but it is not used here. Fix: call `loadGraph()` on mount and reserve `rebuildGraph()` for the explicit toolbar button.

**Orphaned `ResizeObserver` on graph data changes** (`GraphCanvas.vue:297-304`). The `ResizeObserver` is created once in `onMounted` and stored in the module-level `resizeObserver` variable. When the `watch` on `[props.nodes, props.edges]` fires and calls `buildGraph()`, the old `force-graph` instance is destroyed and a new one is created, but the `ResizeObserver` is not disconnected and re-attached to the new instance's container reference. The observer continues to fire against the old DOM element, calling `graph.width()` and `graph.height()` on the now-replaced instance. Over multiple data refreshes within a single page visit this leaks observer registrations. Fix: disconnect and re-attach the `ResizeObserver` inside `buildGraph`, or use a separate `watch` that only resizes without rebuilding.
