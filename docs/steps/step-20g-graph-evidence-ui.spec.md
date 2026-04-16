# Step 20g — Graph Evidence UI: Edge Tooltips + Chunk Preview

> **Goal**: Make the new chunk-level evidence from step 20c visible in the
> graph UI. When a user hovers or clicks a `similar_to` edge, show *why*
> two notes are connected — which specific sections matched and with what
> similarity score. Also surface evidence in the node preview sidebar.

**Status**: ⬜ Not started
**Depends on**: Step 20c (chunk-level graph edges with evidence metadata)
**Effort**: ~0.5 day

---

## Why This Matters

After step 20c, the backend sends edges like:

```json
{
  "source": "note:health/sleep-tracking.md",
  "target": "note:health/evening-routine.md",
  "type": "similar_to",
  "weight": 0.85,
  "evidence": [
    {"source_chunk": 2, "target_chunk": 1, "similarity": 0.87},
    {"source_chunk": 0, "target_chunk": 3, "similarity": 0.72}
  ]
}
```

But the frontend currently ignores `evidence` — it doesn't appear in the
`GraphEdge` type, and there's no tooltip on edge hover. The graph shows
connections but can't explain *why* they exist.

This step closes that gap: the user hovers a dashed `similar_to` line
and sees "Connected: 'Sleep Tracking' section ↔ 'Evening Routine' section (87% similar)".
This makes the semantic graph **debuggable and trustworthy** instead of magical.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `GraphEdge` type extension | Add optional `evidence` + `weight` fields |
| Edge hover tooltip | Show evidence details on `similar_to` edge hover |
| Edge click → node preview | Click edge to see full evidence in sidebar |
| Evidence in `GraphNodePreview` | "Similar connections" section with chunk evidence |
| Edge weight visualization | `similar_to` edge opacity/width varies by weight |

**What this step does NOT cover**:
- Edge creation UI (already exists at `POST /api/graph/edges`)
- Evidence for non-`similar_to` edges (those are structural, not semantic)
- Chunk text preview (would require new API endpoint — deferred)

---

## File Structure

```
frontend/
  app/
    types/index.ts                # MODIFY — extend GraphEdge
    components/
      GraphCanvas.vue             # MODIFY — edge hover tooltip, weight-based styling
      GraphNodePreview.vue        # MODIFY — evidence section for similar connections
    composables/
      useGraph.ts                 # MODIFY — pass edge data with evidence
```

---

## Implementation Details

### 1. `types/index.ts` — Extend `GraphEdge`

Current (`types/index.ts:132-137`):
```ts
export interface GraphEdge {
  source: string
  target: string
  type: string
  weight: number
}
```

New:
```ts
export interface ChunkEvidence {
  source_chunk: number
  target_chunk: number
  similarity: number
}

export interface GraphEdge {
  source: string
  target: string
  type: string
  weight: number
  evidence?: ChunkEvidence[]
}
```

This is backwards compatible — `evidence` is optional. Old graph data
without evidence still parses correctly.

### 2. `GraphCanvas.vue` — Edge Hover Tooltip

Currently the tooltip only works for nodes (`hoveredNode`). Add edge hover:

**Data refs**:
```ts
const hoveredEdge = ref<GraphEdge | null>(null)
const hoveredEdgePosition = ref({ x: 0, y: 0 })
```

**In `buildGraph()`**, add edge hover handler after the existing `onNodeHover`:

```ts
.onLinkHover((link: any, prevLink: any) => {
  if (link) {
    // Find the original edge with evidence metadata
    const edge = props.edges.find(
      e => (e.source === link.source?.id && e.target === link.target?.id)
        || (e.source === link.target?.id && e.target === link.source?.id)
    )
    hoveredEdge.value = edge ?? null
  } else {
    hoveredEdge.value = null
  }
})
```

**Tooltip template** (add below the existing node tooltip):

```html
<div v-if="hoveredEdge && hoveredEdge.type === 'similar_to'" class="graph-canvas__edge-tooltip">
  <div class="graph-canvas__edge-tooltip-header">
    <span class="graph-canvas__edge-tooltip-type">Semantic Connection</span>
    <span class="graph-canvas__edge-tooltip-weight">{{ Math.round((hoveredEdge.weight ?? 0) * 100) }}%</span>
  </div>
  <div v-if="hoveredEdge.evidence?.length" class="graph-canvas__edge-tooltip-evidence">
    <div
      v-for="(ev, i) in hoveredEdge.evidence.slice(0, 3)"
      :key="i"
      class="graph-canvas__edge-tooltip-pair"
    >
      Section {{ ev.source_chunk }} ↔ Section {{ ev.target_chunk }}
      <span class="graph-canvas__edge-tooltip-sim">{{ Math.round(ev.similarity * 100) }}%</span>
    </div>
  </div>
  <div v-else class="graph-canvas__edge-tooltip-note">
    Similarity based on note content
  </div>
</div>
```

**Note**: force-graph doesn't provide screen coordinates for link hover.
Position the tooltip at cursor position using a `mousemove` listener on the
container, updating `tooltipStyle` on each move:

```ts
// In onMounted:
containerRef.value?.addEventListener('mousemove', (e) => {
  tooltipStyle.value = {
    left: `${e.offsetX + 15}px`,
    top: `${e.offsetY - 10}px`,
  }
})
```

This reuses the existing `tooltipStyle` ref (already used for node tooltip).

### 3. `GraphCanvas.vue` — Weight-Based Edge Styling

Current `similar_to` styling is uniform. Make it vary by weight:

```ts
.linkWidth((link: any) => {
  const type = link._type || 'tagged'
  if (type === 'similar_to') {
    // Weight 0.3–1.0 → width 0.8–2.5
    const w = link._weight ?? 0.5
    return 0.8 + w * 1.7
  }
  if (type === 'linked' || type === 'related') return 3.5
  if (type === 'part_of') return 1.2
  return 2
})

.linkColor((link: any) => {
  const type = link._type || 'tagged'
  if (type === 'similar_to') {
    // Stronger connections = more opaque
    const w = link._weight ?? 0.5
    const opacity = 0.3 + w * 0.5
    return `rgba(129, 140, 248, ${opacity})`
  }
  return EDGE_COLOR[type] ?? 'rgba(100, 160, 220, 0.15)'
})
```

Update the `graphData` construction to pass weight:

```ts
links: edges
  .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
  .map(e => ({
    source: e.source,
    target: e.target,
    _type: e.type,
    _weight: e.weight,   // NEW
    _evidence: e.evidence, // NEW (for tooltip lookup)
  })),
```

### 4. `GraphNodePreview.vue` — Evidence Section

When a node is selected that has `similar_to` edges with evidence, show them
in the sidebar. This requires getting the edges from the graph data.

**Add prop**:
```ts
const props = defineProps<{
  node: GraphNode
  similarEdges?: GraphEdge[]  // NEW — filtered similar_to edges for this node
}>()
```

**In `graph.vue`**, compute and pass similar edges:
```ts
const selectedSimilarEdges = computed(() => {
  if (!selectedNode.value) return []
  const nodeId = selectedNode.value.id
  return graph.value.edges.filter(
    e => e.type === 'similar_to' && (e.source === nodeId || e.target === nodeId)
  )
})
```

```html
<GraphNodePreview
  v-if="selectedNode"
  :node="selectedNode"
  :similar-edges="selectedSimilarEdges"
  @close="selectNode(null)"
  ...
/>
```

**In `GraphNodePreview.vue`**, add a "Semantic Connections" section:

```html
<!-- Semantic connections with evidence -->
<div v-if="similarEdges?.length" class="node-preview__section">
  <h4 class="node-preview__section-label">Semantic Connections</h4>
  <ul class="node-preview__sim-list">
    <li
      v-for="edge in similarEdges.slice(0, 5)"
      :key="edge.source + edge.target"
      class="node-preview__sim-item"
      @click="navigateToOther(edge)"
    >
      <div class="node-preview__sim-header">
        <span class="node-preview__sim-label">{{ otherNodeLabel(edge) }}</span>
        <span class="node-preview__sim-score">{{ Math.round(edge.weight * 100) }}%</span>
      </div>
      <div v-if="edge.evidence?.length" class="node-preview__sim-evidence">
        <span v-for="(ev, i) in edge.evidence.slice(0, 2)" :key="i" class="node-preview__sim-chunk">
          §{{ ev.source_chunk }} ↔ §{{ ev.target_chunk }} ({{ Math.round(ev.similarity * 100) }}%)
        </span>
      </div>
    </li>
  </ul>
</div>
```

Helper methods:
```ts
function otherNodeLabel(edge: GraphEdge): string {
  const otherId = edge.source === props.node.id ? edge.target : edge.source
  // Look up label from connected_notes or fallback to ID
  const note = detail.value?.connected_notes.find(n => n.id === otherId)
  return note?.label ?? otherId.replace('note:', '').replace('.md', '')
}

function navigateToOther(edge: GraphEdge): void {
  const otherId = edge.source === props.node.id ? edge.target : edge.source
  emit('navigate-node', otherId)
}
```

---

## Styling

### Edge Tooltip

```css
.graph-canvas__edge-tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 20;
  background: rgba(6, 8, 13, 0.94);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(129, 140, 248, 0.3);  /* indigo for semantic */
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.72rem;
  color: var(--text-primary);
  box-shadow: 0 0 20px rgba(129, 140, 248, 0.08);
  max-width: 260px;
}

.graph-canvas__edge-tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.graph-canvas__edge-tooltip-type {
  font-size: 0.62rem;
  color: rgba(165, 180, 252, 0.8);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.graph-canvas__edge-tooltip-weight {
  font-size: 0.72rem;
  font-weight: 600;
  color: rgba(165, 180, 252, 1);
}

.graph-canvas__edge-tooltip-pair {
  font-size: 0.65rem;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
}

.graph-canvas__edge-tooltip-sim {
  color: rgba(165, 180, 252, 0.8);
  font-weight: 500;
}

.graph-canvas__edge-tooltip-note {
  font-size: 0.62rem;
  color: var(--text-muted);
  font-style: italic;
}
```

### Node Preview — Similar Connections

```css
.node-preview__sim-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.node-preview__sim-item {
  padding: 0.35rem 0.4rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
  border-left: 2px solid rgba(129, 140, 248, 0.3);
  margin-bottom: 0.3rem;
}

.node-preview__sim-item:hover {
  background: var(--bg-surface);
  border-left-color: rgba(129, 140, 248, 0.7);
}

.node-preview__sim-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-preview__sim-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.node-preview__sim-score {
  font-size: 0.68rem;
  color: rgba(165, 180, 252, 0.9);
  font-weight: 600;
}

.node-preview__sim-evidence {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.15rem;
}

.node-preview__sim-chunk {
  font-size: 0.6rem;
  color: var(--text-muted);
  background: var(--bg-surface);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
}
```

---

## Visual Design

Edge tooltip on hover:
```
┌────────────────────────────┐
│  SEMANTIC CONNECTION   85% │
│  Section 2 ↔ Section 1 87%│
│  Section 0 ↔ Section 3 72%│
└────────────────────────────┘
```

Node preview sidebar — "Semantic Connections" section:
```
SEMANTIC CONNECTIONS
┌──────────────────────────┐
│ │ Evening Routine    85% │
│ │ §2 ↔ §1 (87%)  §0↔§3  │
├──────────────────────────┤
│ │ Meditation Notes   71% │
│ │ §1 ↔ §2 (73%)         │
└──────────────────────────┘
```

---

## Future Enhancement (out of scope)

When chunk text preview is needed (e.g., "show me what section matched"),
add a backend endpoint:

```
GET /api/graph/edge-evidence?source=note:a.md&target=note:b.md
→ returns chunk text for each evidence pair
```

This requires reading chunks from `note_chunks` table. Deferred because
it's not needed for the core UX — section indices + similarity scores
are enough to make the graph debuggable.

---

## Test Cases

```
# Manual testing (visual)

- Hover a similar_to edge → tooltip shows "Semantic Connection" + weight
- Hover a similar_to edge WITH evidence → tooltip shows chunk pairs
- Hover a non-similar_to edge → no tooltip (or standard type label)
- Strong similar_to edge (0.9+) → thicker, more opaque line
- Weak similar_to edge (0.3) → thin, faint line
- Click node with similar_to edges → sidebar shows "Semantic Connections" section
- Click a connection in sidebar → navigates to the other node
- Graph with no similar_to edges → no tooltip, no sidebar section (no errors)
- Old graph data without evidence field → renders normally, no errors
```

---

## Acceptance Criteria

- [ ] `GraphEdge` type includes optional `evidence: ChunkEvidence[]`
- [ ] `similar_to` edge hover shows tooltip with weight + evidence pairs
- [ ] `similar_to` edge width/opacity varies by weight (0.3 → thin/faint, 1.0 → thick/bright)
- [ ] `GraphNodePreview` shows "Semantic Connections" section with evidence
- [ ] Clicking a semantic connection navigates to the other node
- [ ] Non-`similar_to` edges are unaffected (no tooltip, existing styling)
- [ ] Old graph data without `evidence` field renders without errors
- [ ] `_weight` passed through force-graph link data for styling
- [ ] Tooltip positioned near cursor, doesn't overflow viewport
- [ ] All existing graph tests pass (no regressions)
