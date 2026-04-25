<template>
  <div class="graph-canvas">
    <div ref="containerRef" class="graph-canvas__container" />
    <div class="graph-canvas__controls">
      <button @click="zoomToFit" class="graph-canvas__btn">🏠 Fit</button>
      <button @click="zoomIn" class="graph-canvas__btn">＋</button>
      <button @click="zoomOut" class="graph-canvas__btn">－</button>
    </div>
    <div v-if="hoveredNode" class="graph-canvas__tooltip" :style="tooltipStyle">
      <strong>{{ hoveredNode.label }}</strong>
      <span class="graph-canvas__tooltip-type">{{ hoveredNode.type }}{{ hoveredNode.folder ? ' · ' + hoveredNode.folder : '' }}</span>
      <span class="graph-canvas__tooltip-degree" v-if="hoveredDegree > 0">{{ hoveredDegree }} connections</span>
    </div>
    <div v-if="hoveredEdge && hoveredEdge.type === 'similar_to'" class="graph-canvas__edge-tooltip" :style="tooltipStyle">
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
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import type { GraphNode, GraphEdge } from '~/types'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightedNode?: string | null
  searchMatchedIds?: Set<string>
  glowLevel?: 'off' | 'normal' | 'high' | 'mono'
}>()

const emit = defineEmits<{
  nodeClick: [node: GraphNode]
}>()

const containerRef = ref<HTMLElement | null>(null)
const hoveredNode = ref<GraphNode | null>(null)
const hoveredEdge = ref<GraphEdge | null>(null)
const hoveredDegree = ref(0)
const tooltipStyle = ref({ left: '0px', top: '0px' })

let graph: any = null
let resizeObserver: ResizeObserver | null = null

// --- Per-instance render state (recomputed on data change, read by draw callbacks) ---
let degrees: Record<string, number> = {}
let adjacency: Record<string, Set<string>> = {}
let sprintMembership: Record<string, string> = {}
let sprintInitialPos: Record<string, { x: number; y: number }> = {}
let perfMode = false          // true when graph is big → disable particles, shadows, halos
let hoverRafPending = false   // throttle hover re-paints to one per animation frame
// O(1) edge lookup keyed by "source|target|type" — onLinkHover used to do a
// linear scan of props.edges per mouse-move event.
let edgeIndex: Map<string, GraphEdge> = new Map()
let nodeIndex: Map<string, GraphNode> = new Map()

// Gradient cache: avoid allocating fresh radial gradients every draw.
// Keyed by "type|roundedRadius". Invalidated when the canvas context changes
// (which happens on ForceGraph rebuild).
const gradientCache = new Map<string, {
  halo: CanvasGradient
  body: CanvasGradient
}>()
let gradientCtx: CanvasRenderingContext2D | null = null

function gradKey(type: string, r: number): string {
  return `${type}|${Math.round(r)}`
}

// Build (once per node type/size) the reusable gradients. Returned gradients
// are CENTERED AT (0,0); draw code must translate the canvas first.
function getNodeGradients(
  ctx: CanvasRenderingContext2D,
  type: string,
  r: number,
  color: string,
  glow: string,
): { halo: CanvasGradient; body: CanvasGradient } {
  if (gradientCtx !== ctx) {
    gradientCache.clear()
    gradientCtx = ctx
  }
  const key = gradKey(type, r)
  const cached = gradientCache.get(key)
  if (cached) return cached
  const halo = ctx.createRadialGradient(0, 0, r * 0.3, 0, 0, r + 12)
  halo.addColorStop(0, glow.replace(/[\d.]+\)$/, '0.5)'))
  halo.addColorStop(0.55, glow.replace(/[\d.]+\)$/, '0.2)'))
  halo.addColorStop(1, glow.replace(/[\d.]+\)$/, '0.0)'))
  const body = ctx.createRadialGradient(-r * 0.25, -r * 0.25, 0, 0, 0, r)
  body.addColorStop(0, 'rgba(255,255,255,0.55)')
  body.addColorStop(0.4, color)
  body.addColorStop(1, glow.replace(/[\d.]+\)$/, '0.8)'))
  const entry = { halo, body }
  gradientCache.set(key, entry)
  return entry
}

// --- Color palette ---
const NODE_COLOR: Record<string, string> = {
  // Core Jarvis types
  note:   'rgba(2, 254, 255, 1)',     // cyan
  tag:    '#34d399',                  // emerald
  person: '#c084fc',                  // violet
  area:   '#fb923c',                  // orange
  // Entity types extracted from notes (Step 25 PR 2)
  org:           '#facc15',           // amber       — organisations
  project:       '#f472b6',           // pink        — projects (note-derived)
  place:         '#22d3ee',           // teal        — places
  // Provenance / batch nodes (Step 25 PR 5)
  source:        '#a3e635',           // lime        — derived_from sources
  batch:         '#94a3b8',           // slate       — same_batch groups
  // TF-IDF concept bridges (Step 27)
  concept:       '#fde047',           // soft yellow — distinctive concepts
  // Jira projection
  jira_issue:     '#60a5fa',          // sky blue  — generic issue
  jira_epic:      '#f472b6',          // pink      — epics pop
  jira_project:   '#facc15',          // amber     — projects big & bright
  jira_person:    '#c084fc',          // violet    — same as person
  jira_sprint:    '#22d3ee',          // teal      — sprints
  jira_label:     '#a3e635',          // lime      — labels
  jira_component: '#f97316',          // orange-red — components
}

const NODE_GLOW: Record<string, string> = {
  note:   'rgba(2, 254, 255, 0.5)',
  tag:    'rgba(52, 211, 153, 0.5)',
  person: 'rgba(192, 132, 252, 0.5)',
  area:   'rgba(251, 146, 60, 0.5)',
  org:            'rgba(250, 204, 21, 0.5)',
  project:        'rgba(244, 114, 182, 0.5)',
  place:          'rgba(34, 211, 238, 0.5)',
  source:         'rgba(163, 230, 53, 0.45)',
  batch:          'rgba(148, 163, 184, 0.4)',
  concept:        'rgba(253, 224, 71, 0.45)',
  jira_issue:     'rgba(96, 165, 250, 0.5)',
  jira_epic:      'rgba(244, 114, 182, 0.6)',
  jira_project:   'rgba(250, 204, 21, 0.55)',
  jira_person:    'rgba(192, 132, 252, 0.5)',
  jira_sprint:    'rgba(34, 211, 238, 0.5)',
  jira_label:     'rgba(163, 230, 53, 0.45)',
  jira_component: 'rgba(249, 115, 22, 0.5)',
}

// --- Monochrome palette ----------------------------------------------------
// Used when glowLevel === 'mono'. Three tiers of grey/white render the
// graph as an elegant ink drawing on the dark background. No glows, no
// halos, no particles — just structure.
const MONO_NODE_COLOR: Record<string, string> = {
  // Major anchors — pure white
  area:           'rgba(255, 255, 255, 0.96)',
  jira_project:   'rgba(255, 255, 255, 0.96)',
  jira_epic:      'rgba(255, 255, 255, 0.92)',
  jira_sprint:    'rgba(255, 255, 255, 0.88)',
  // Mid tier — light grey
  note:           'rgba(220, 220, 222, 0.85)',
  person:         'rgba(220, 220, 222, 0.85)',
  jira_person:    'rgba(220, 220, 222, 0.85)',
  jira_component: 'rgba(200, 200, 204, 0.78)',
  // Minor — dimmer grey
  jira_issue:     'rgba(170, 172, 178, 0.72)',
  tag:            'rgba(150, 152, 158, 0.65)',
  jira_label:     'rgba(150, 152, 158, 0.65)',
}
const MONO_DEFAULT_COLOR = 'rgba(170, 172, 178, 0.7)'
const MONO_EDGE_COLOR = 'rgba(220, 220, 224, 0.18)'
const MONO_EDGE_FOCUS = 'rgba(255, 255, 255, 0.85)'
const MONO_EDGE_DIM = 'rgba(220, 220, 224, 0.04)'

const EDGE_COLOR: Record<string, string> = {
  tagged:   'rgba(52, 211, 153, 0.7)',
  part_of:  'rgba(251, 146, 60, 0.55)',
  linked:   'rgba(2, 254, 255, 0.75)',
  mentions: 'rgba(192, 132, 252, 0.7)',
  related:  'rgba(2, 254, 255, 0.65)',
  similar_to: 'rgba(129, 140, 248, 0.6)', // indigo for semantic similarity
  about_concept: 'rgba(253, 224, 71, 0.55)', // yellow — TF-IDF concept bridges
  co_mentioned: 'rgba(244, 114, 182, 0.55)', // pink — entities sharing a note
  temporal: 'rgba(250, 204, 21, 0.35)',
  // Jira edges
  in_project:        'rgba(250, 204, 21, 0.55)',  // amber (project)
  in_epic:           'rgba(244, 114, 182, 0.75)', // pink (epic)
  is_epic_shadow:    'rgba(244, 114, 182, 0.35)',
  parent_of:         'rgba(96, 165, 250, 0.7)',   // sky blue (hierarchy)
  blocks:            'rgba(239, 68, 68, 0.85)',   // red — blocks
  depends_on:        'rgba(239, 68, 68, 0.6)',
  duplicate_of:      'rgba(148, 163, 184, 0.55)', // slate
  relates_to:        'rgba(96, 165, 250, 0.5)',
  assigned_to:       'rgba(192, 132, 252, 0.6)',  // violet (person)
  in_sprint:         'rgba(34, 211, 238, 0.6)',   // teal
  has_label:         'rgba(163, 230, 53, 0.55)',  // lime
  has_component:     'rgba(249, 115, 22, 0.6)',   // orange
  commented_on:      'rgba(192, 132, 252, 0.4)',
}

const EDGE_PARTICLE_COLOR: Record<string, string> = {
  tagged:   'rgba(52, 211, 153, 0.7)',
  part_of:  'rgba(251, 146, 60, 0.5)',
  linked:   'rgba(2, 254, 255, 0.8)',
  mentions: 'rgba(192, 132, 252, 0.7)',
  related:  'rgba(2, 254, 255, 0.7)',
  similar_to: 'rgba(165, 180, 252, 0.7)',
  temporal: 'rgba(250, 204, 21, 0.3)',
}

// --- Compute degree per node (for sizing) ---
// NOTE: kept only for reference — the real work happens in `recomputeDerived`
// below, which fuses degrees + adjacency in a single pass over edges.
// (Intentionally unused; left here so future callers have a lightweight helper.)
function computeDegrees(): Record<string, number> {
  const deg: Record<string, number> = {}
  const nodes = props.nodes ?? []
  const edges = props.edges ?? []
  const nodeIds = new Set(nodes.map(n => n.id))
  for (const e of edges) {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue
    deg[e.source] = (deg[e.source] || 0) + 1
    deg[e.target] = (deg[e.target] || 0) + 1
  }
  return deg
}
void computeDegrees  // silence "declared but never used"

// --- Compute sprint membership: issueId -> sprintId ---
// Each Jira issue with an `in_sprint` edge is pulled toward its sprint node
// by the cluster force below, so each sprint forms a visible "ball".
//
// A ticket can belong to many sprints (e.g. moved from Sprint 42 → Sprint 43).
// We pick the sprint with the highest number in its label as the "home"
// cluster — this keeps tickets grouped by their most recent sprint even
// after that sprint is closed. Active sprints break ties. Sprints without
// any number fall back to first-seen order.
function computeSprintMembership(): Record<string, string> {
  const sprintNumber: Record<string, number> = {}
  const sprintIsActive: Record<string, boolean> = {}
  for (const n of props.nodes ?? []) {
    if (n.type !== 'jira_sprint') continue
    const match = (n.label ?? '').match(/(\d+)/)
    if (match && match[1]) sprintNumber[n.id] = parseInt(match[1], 10)
    sprintIsActive[n.id] = (n.folder ?? '').toLowerCase() === 'active'
  }

  const map: Record<string, string> = {}
  for (const e of props.edges ?? []) {
    if (e.type !== 'in_sprint') continue
    const current = map[e.source]
    if (!current) {
      map[e.source] = e.target
      continue
    }
    const curNum = sprintNumber[current] ?? -1
    const newNum = sprintNumber[e.target] ?? -1
    if (newNum > curNum) {
      map[e.source] = e.target
    } else if (newNum === curNum && sprintIsActive[e.target] && !sprintIsActive[current]) {
      map[e.source] = e.target
    }
  }
  return map
}

function nodeRadius(type: string, degree: number): number {
  // Bigger, more prominent: projects & epics (anchors of the Jira graph)
  const baseByType: Record<string, number> = {
    area: 7,
    jira_project: 9,
    jira_epic: 8,
    jira_sprint: 6,
    person: 5,
    jira_person: 5,
    note: 4,
    jira_issue: 4,
    jira_component: 3.5,
    jira_label: 3,
    tag: 3,
  }
  const base = baseByType[type] ?? 3
  return base + Math.min(degree * 0.4, 8)
}

// --- Derived state recomputation (degrees / adjacency / sprint layout) -----
// Called once at init and then on every data change. Writes to module-level
// `let` vars that the ForceGraph draw callbacks read on every frame.
function recomputeDerived() {
  const nodes = props.nodes ?? []
  const edges = props.edges ?? []

  // Degrees
  const deg: Record<string, number> = {}
  const nodeIds = new Set(nodes.map(n => n.id))
  // Adjacency
  const adj: Record<string, Set<string>> = {}
  for (const e of edges) {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue
    deg[e.source] = (deg[e.source] || 0) + 1
    deg[e.target] = (deg[e.target] || 0) + 1
    ;(adj[e.source] ??= new Set()).add(e.target)
    ;(adj[e.target] ??= new Set()).add(e.source)
  }
  degrees = deg
  adjacency = adj

  // Sprint membership + ring layout
  sprintMembership = computeSprintMembership()
  const sprintNodes = nodes.filter(n => n.type === 'jira_sprint')
  sprintNodes.sort((a, b) => {
    const an = parseInt((a.label ?? '').match(/(\d+)/)?.[1] ?? '0', 10)
    const bn = parseInt((b.label ?? '').match(/(\d+)/)?.[1] ?? '0', 10)
    return an - bn
  })
  sprintInitialPos = {}
  if (sprintNodes.length > 0) {
    const CLUSTER_GAP = 240
    const ringRadius = sprintNodes.length === 1
      ? 0
      : Math.max(200, (CLUSTER_GAP * sprintNodes.length) / (2 * Math.PI))
    sprintNodes.forEach((n, i) => {
      const angle = (i / sprintNodes.length) * 2 * Math.PI
      sprintInitialPos[n.id] = {
        x: Math.cos(angle) * ringRadius,
        y: Math.sin(angle) * ringRadius,
      }
    })
  }

  // Perf mode kicks in once the graph is large enough that shadowBlur +
  // per-edge particles become the bottleneck (empirical threshold).
  perfMode = nodes.length > 250 || edges.length > 1200

  // Build O(1) edge-index so onLinkHover does not have to linear-scan.
  edgeIndex = new Map()
  for (const e of edges) {
    edgeIndex.set(`${e.source}|${e.target}|${e.type}`, e)
  }
  nodeIndex = new Map(nodes.map(n => [n.id, n]))
}

// Update the force-graph data in place — cheap compared to teardown +
// rebuild. Preserves physics state and simulation positions.
function updateGraphData() {
  if (!graph) return
  recomputeDerived()
  const nodes = props.nodes ?? []
  const edges = props.edges ?? []
  const nodeIds = new Set(nodes.map(n => n.id))

  // Preserve existing node positions so the user's view doesn't jump on
  // filter changes. ForceGraph keeps its own mutated node list on the
  // simulation; we merge those positions into the new node objects.
  const oldData = graph.graphData()
  const oldPos = new Map<string, { x: number; y: number; vx: number; vy: number }>()
  for (const n of oldData.nodes) {
    if (Number.isFinite(n.x) && Number.isFinite(n.y)) {
      oldPos.set(n.id, { x: n.x, y: n.y, vx: n.vx ?? 0, vy: n.vy ?? 0 })
    }
  }

  const nextNodes = nodes.map(n => {
    const copy: any = { ...n }
    const kept = oldPos.get(n.id)
    if (kept) {
      copy.x = kept.x; copy.y = kept.y; copy.vx = kept.vx; copy.vy = kept.vy
    } else if (n.type === 'jira_sprint' && sprintInitialPos[n.id]) {
      copy.x = sprintInitialPos[n.id]!.x
      copy.y = sprintInitialPos[n.id]!.y
    } else if (n.type === 'jira_issue' && sprintMembership[n.id]) {
      const anchor = sprintInitialPos[sprintMembership[n.id]!]
      if (anchor) {
        copy.x = anchor.x + (Math.random() - 0.5) * 80
        copy.y = anchor.y + (Math.random() - 0.5) * 80
      }
    }
    return copy
  })

  const nextLinks = edges
    .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map(e => ({ source: e.source, target: e.target, _type: e.type, _weight: e.weight, _evidence: e.evidence }))

  graph.graphData({ nodes: nextNodes, links: nextLinks })
  // A short reheat helps the simulation settle after a filter change,
  // but we skip the 80-tick warmup of a full rebuild.
  graph.d3ReheatSimulation?.()
}

async function buildGraph() {
  if (!containerRef.value) return
  // Fast path: if the graph already exists, just swap data in place.
  if (graph) {
    updateGraphData()
    return
  }
  const el = containerRef.value

  // Disconnect previous ResizeObserver before rebuilding
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  el.innerHTML = ''

  if (props.nodes.length === 0) return

  const { default: ForceGraph } = await import('force-graph')
  // Populate module-level degrees / adjacency / sprintMembership / sprintInitialPos / perfMode
  recomputeDerived()

  graph = new ForceGraph(el)
    .backgroundColor('#06080d')
    .width(el.clientWidth)
    .height(el.clientHeight)
    .nodeId('id')
    .nodeLabel('')
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return

      const deg = degrees[node.id] || 0
      const r = nodeRadius(node.type, deg)
      const isMono = props.glowLevel === 'mono'
      const color = isMono
        ? (MONO_NODE_COLOR[node.type] ?? MONO_DEFAULT_COLOR)
        : (NODE_COLOR[node.type] ?? '#9ca3af')
      const glowColor = isMono
        ? 'rgba(255, 255, 255, 0.0)'
        : (NODE_GLOW[node.type] ?? 'rgba(156, 163, 175, 0.3)')
      const isHighlighted = props.highlightedNode === node.id
      const isHovered = hoveredNode.value?.id === node.id
      // "Focus" = hover takes priority, but when nothing is hovered and a
      // node is clicked (highlightedNode), it acts as sticky hover — the
      // clicked node + its neighbors stay lit until the panel is closed.
      const focusId = hoveredNode.value?.id ?? props.highlightedNode ?? null
      const isFocused = node.id === focusId
      const isFocusNeighbor = !!focusId && adjacency[focusId]?.has(node.id)
      const isSearchActive = props.searchMatchedIds && props.searchMatchedIds.size > 0
      const isSearchMatch = isSearchActive && props.searchMatchedIds!.has(node.id)
      const searchDims = isSearchActive && !isSearchMatch && !isFocused
      const focusDims = !!focusId && !isFocused && !isFocusNeighbor
      const isDimmed = searchDims || focusDims
      const isSpecial = isHighlighted || isHovered || isFocused || isFocusNeighbor

      if (isDimmed) {
        ctx.globalAlpha = focusDims ? 0.08 : 0.15
      }

      // LOD: at low zoom, or in perf mode for non-special nodes, skip the
      // expensive halo + shadowBlur and draw a flat circle. This is where
      // the bulk of the perf win comes from (shadowBlur is ~10× more
      // expensive than a plain fill in Canvas2D).
      // Glow level overrides:
      //  - 'off'    → always flat (fastest)
      //  - 'normal' → perfMode still suppresses glow for non-special nodes
      //  - 'high'   → user explicitly asked for full bloom, ignore perfMode
      //  - 'mono'   → elegant b/w — always flat, no halos, no shadows
      const glow = props.glowLevel ?? 'normal'
      const lowDetail =
        glow === 'off' ||
        glow === 'mono' ||
        globalScale < 0.45
      // In normal+perfMode non-special nodes still get the halo gradient
      // but skip the expensive shadowBlur (the real perf killer).
      const skipShadow =
        glow === 'normal' && perfMode && !isSpecial

      if (lowDetail) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
        ctx.fillStyle = color
        ctx.fill()
      } else {
        // Cached, pre-built gradients — translated into place instead of
        // recreated per draw. One halo layer (was three) is visually close
        // to the original at normal zoom.
        const grads = getNodeGradients(ctx, node.type, r, color, glowColor)
        const glowMult = glow === 'high' ? 1.6 : 1.0
        ctx.save()
        ctx.translate(node.x, node.y)

        // Halo — in 'high' mode draw an extra outer layer for visible bloom.
        if (glow === 'high') {
          ctx.beginPath()
          ctx.arc(0, 0, (r + 12) * 1.35, 0, 2 * Math.PI)
          ctx.fillStyle = grads.halo
          ctx.globalAlpha = (ctx.globalAlpha as number) * 0.45
          ctx.fill()
          ctx.globalAlpha = isDimmed ? (focusDims ? 0.08 : 0.15) : 1.0
        }
        ctx.beginPath()
        ctx.arc(0, 0, r + 12, 0, 2 * Math.PI)
        ctx.fillStyle = grads.halo
        ctx.fill()

        // Node body — shadowBlur ONLY for special nodes (hover / focus /
        // highlight) or 'high' mode. In normal+perfMode we skip shadow
        // entirely but still keep the halo gradient above.
        if (skipShadow) {
          // no shadowBlur — halo gradient alone provides subtle glow
        } else if (isSpecial) {
          ctx.shadowColor = color
          ctx.shadowBlur = (isHighlighted ? 50 : 32) * glowMult
        } else if (glow === 'high') {
          ctx.shadowColor = color
          ctx.shadowBlur = 18
        }
        ctx.beginPath()
        ctx.arc(0, 0, r, 0, 2 * Math.PI)
        ctx.fillStyle = grads.body
        ctx.fill()
        if (isSpecial || glow === 'high') ctx.shadowBlur = 0

        // Thin edge ring — skip in perf mode (another stroke per node = real cost).
        if (!perfMode || isSpecial) {
          ctx.strokeStyle = 'rgba(255,255,255,0.22)'
          ctx.lineWidth = 0.6
          ctx.stroke()
        }
        ctx.restore()
      }

      // Label logic: always show for area; for other types respect zoom + focus.
      // In perf mode we raise the degree threshold to cut out hundreds of text draws.
      const labelDegThreshold = perfMode ? 8 : 4
      const showLabel =
        node.type === 'area' ||
        deg >= labelDegThreshold ||
        isHovered ||
        isHighlighted ||
        globalScale > 1.2

      if (showLabel) {
        const maxFontSize = node.type === 'area' ? 6 : node.type === 'tag' ? 3.5 : 4.5
        const fontSize = Math.min(14 / globalScale, maxFontSize)
        const alpha = node.type === 'tag' ? 0.5 : 0.85

        ctx.font = `${node.type === 'area' ? 'bold ' : ''}${fontSize}px Inter, system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`

        // Truncate long labels
        let label = node.label
        if (label.length > 25 && !isHovered) {
          label = label.slice(0, 22) + '…'
        }

        ctx.fillText(label, node.x, node.y + r + 2)
      }

      // Reset alpha after drawing dimmed node
      if (isDimmed) {
        ctx.globalAlpha = 1.0
      }
    })
    .nodePointerAreaPaint((node: any, color: string, ctx: CanvasRenderingContext2D) => {
      const deg = degrees[node.id] || 0
      const r = nodeRadius(node.type, deg) + 4
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
    })
    // --- Edge styling by type ---
    .linkColor((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      // Focus dimming: hover > click. When a node is focused, dim edges
      // that don't touch it; boost edges that DO touch it.
      const focusId = hoveredNode.value?.id ?? props.highlightedNode ?? null
      const touchesFocus = !!focusId && (srcId === focusId || tgtId === focusId)
      const isMono = props.glowLevel === 'mono'
      if (isMono) {
        if (focusId && !touchesFocus) return MONO_EDGE_DIM
        if (props.searchMatchedIds && props.searchMatchedIds.size > 0) {
          if (!props.searchMatchedIds.has(srcId) && !props.searchMatchedIds.has(tgtId)) {
            return MONO_EDGE_DIM
          }
        }
        return touchesFocus ? MONO_EDGE_FOCUS : MONO_EDGE_COLOR
      }
      if (focusId && !touchesFocus) {
        return 'rgba(100, 160, 220, 0.03)'
      }
      // Dim edges during search if neither endpoint is matched
      if (props.searchMatchedIds && props.searchMatchedIds.size > 0) {
        if (!props.searchMatchedIds.has(srcId) && !props.searchMatchedIds.has(tgtId)) {
          return 'rgba(100, 160, 220, 0.03)'
        }
      }
      const type = link._type || 'tagged'
      // Brighten edges touching the focused node
      if (touchesFocus) {
        const brightColor: Record<string, string> = {
          in_sprint:     'rgba(34, 211, 238, 0.95)',
          in_project:    'rgba(250, 204, 21, 0.9)',
          in_epic:       'rgba(244, 114, 182, 0.95)',
          blocks:        'rgba(239, 68, 68, 1.0)',
          depends_on:    'rgba(239, 68, 68, 0.9)',
          assigned_to:   'rgba(192, 132, 252, 0.9)',
          relates_to:    'rgba(96, 165, 250, 0.85)',
          has_label:     'rgba(163, 230, 53, 0.85)',
          has_component: 'rgba(249, 115, 22, 0.9)',
          tagged:        'rgba(52, 211, 153, 0.95)',
          linked:        'rgba(2, 254, 255, 1.0)',
          mentions:      'rgba(192, 132, 252, 0.95)',
          part_of:       'rgba(251, 146, 60, 0.9)',
          related:       'rgba(2, 254, 255, 0.95)',
          similar_to:    'rgba(129, 140, 248, 0.95)',
          commented_on:  'rgba(192, 132, 252, 0.8)',
          parent_of:     'rgba(96, 165, 250, 0.95)',
        }
        return brightColor[type] ?? 'rgba(200, 220, 255, 0.85)'
      }
      if (type === 'similar_to') {
        const w = link._weight ?? 0.5
        const alpha = 0.3 + w * 0.5
        return `rgba(129, 140, 248, ${alpha})`
      }
      return EDGE_COLOR[type] ?? 'rgba(100, 160, 220, 0.15)'
    })
    .linkWidth((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      const focusId = hoveredNode.value?.id ?? props.highlightedNode ?? null
      const touchesFocus = !!focusId && (srcId === focusId || tgtId === focusId)
      const type = link._type || 'tagged'
      let w = 0.7
      if (type === 'linked' || type === 'related') w = 1.8
      else if (type === 'blocks' || type === 'depends_on') w = 1.4
      else if (type === 'in_sprint') w = 0.6
      else if (type === 'in_project') w = 0.5
      else if (type === 'in_epic') w = 0.8
      else if (type === 'part_of') w = 0.7
      else if (type === 'similar_to') w = 0.5 + (link._weight ?? 0) * 1.0
      else if (type === 'temporal') w = 0.5
      else if (type === 'has_label' || type === 'has_component') w = 0.5
      else if (type === 'assigned_to' || type === 'reported_by' || type === 'commented_on') w = 0.4
      return touchesFocus ? Math.max(w * 2.5, 2.0) : w
    })
    .linkLineDash((link: any) => {
      // Mono mode: keep dashes minimal so the diagram stays clean
      if (props.glowLevel === 'mono') return []
      // Focused edges become solid so they pop visually
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      const focusId = hoveredNode.value?.id ?? props.highlightedNode ?? null
      if (focusId && (srcId === focusId || tgtId === focusId)) return []
      if (link._type === 'part_of') return [2, 2]
      if (link._type === 'similar_to') return [3, 3]
      if (link._type === 'temporal') return [1, 3]
      if (link._type === 'in_sprint') return [2, 3]
      if (link._type === 'in_project') return [1, 3]
      if (link._type === 'has_label') return [1, 2]
      if (link._type === 'has_component') return [1, 2]
      if (link._type === 'assigned_to' || link._type === 'reported_by') return [2, 2]
      if (link._type === 'commented_on') return [1, 3]
      return []
    })
    .linkDirectionalArrowLength((link: any) => {
      if (props.glowLevel === 'mono') return 0
      return link._type === 'linked' || link._type === 'related' ? 4 : 0
    })
    .linkDirectionalArrowRelPos(0.85)
    .linkDirectionalParticles((link: any) => {
      // Mono mode: zero motion — elegance over animation.
      if (props.glowLevel === 'mono') return 0
      // In perf mode: focused edges get 2 particles, and a wider ambient
      // subset (~15%) gets 1 particle so dots visibly flow across the graph.
      if (perfMode) {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target
        const focusId = hoveredNode.value?.id ?? props.highlightedNode ?? null
        if (focusId && (srcId === focusId || tgtId === focusId)) return 2
        // Ambient: blocks/depends always animate, ~15% of others get 1 particle
        if (link._type === 'blocks' || link._type === 'depends_on') return 1
        if (link._type === 'in_sprint') return 1  // sprint membership edges carry dots
        const h = ((srcId?.charCodeAt?.(srcId.length - 1) ?? 0) + (tgtId?.charCodeAt?.(tgtId.length - 1) ?? 0)) % 7
        return h === 0 ? 1 : 0
      }
      if (link._type === 'linked') return 2
      if (link._type === 'related') return 1
      if (link._type === 'tagged') return 1
      if (link._type === 'mentions') return 1
      if (link._type === 'in_sprint') return 1
      if (link._type === 'blocks' || link._type === 'depends_on') return 1
      return 0
    })
    .linkDirectionalParticleWidth((link: any) => {
      if (link._type === 'blocks' || link._type === 'depends_on') return 2.5
      if (link._type === 'linked' || link._type === 'related') return 2.2
      if (link._type === 'in_sprint') return 1.6
      if (link._type === 'tagged') return 1.8
      return 1.5
    })
    .linkDirectionalParticleSpeed((link: any) => {
      // Slow, varied speeds — dots drift gently along edges
      if (link._type === 'linked') return 0.004 + Math.random() * 0.003
      if (link._type === 'related') return 0.003 + Math.random() * 0.002
      if (link._type === 'blocks' || link._type === 'depends_on') return 0.003 + Math.random() * 0.002
      if (link._type === 'in_sprint') return 0.002 + Math.random() * 0.002
      if (link._type === 'tagged') return 0.002 + Math.random() * 0.0015
      if (link._type === 'mentions') return 0.003 + Math.random() * 0.002
      if (link._type === 'part_of') return 0.0015 + Math.random() * 0.0015
      if (link._type === 'similar_to') return 0.001 + Math.random() * 0.001
      if (link._type === 'temporal') return 0.0015 + Math.random() * 0.001
      return 0.002 + Math.random() * 0.0015
    })
    .linkDirectionalParticleColor((link: any) => {
      return EDGE_PARTICLE_COLOR[link._type] ?? 'rgba(100, 180, 255, 0.4)'
    })
    .linkCurvature((link: any) => {
      // Slight curve to avoid overlapping straight lines
      return link._type === 'part_of' ? 0.15 : 0
    })
    // When zoomed way out on a big graph, hide low-value noise edges
    // (sprint/project/label/component memberships + similar_to). Focused
    // edges stay visible. Huge repaint win on first render + pan/zoom.
    .linkVisibility((link: any) => {
      if (!perfMode) return true
      const zoom = graph?.zoom?.() ?? 1
      if (zoom >= 0.6) return true
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      const focusId = hoveredNode.value?.id ?? props.highlightedNode ?? null
      if (focusId && (srcId === focusId || tgtId === focusId)) return true
      const noisy = new Set([
        'in_sprint', 'in_project', 'has_label', 'has_component',
        'similar_to', 'commented_on', 'temporal',
      ])
      return !noisy.has(link._type)
    })
    // --- Interaction ---
    .enableNodeDrag(true)
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    // Faster decay + shorter cooldown in perf mode so the physics sim settles
    // and stops burning CPU on graphs with thousands of edges. Smaller
    // warmup also skips a big block of blocking work at render time.
    .d3AlphaDecay(perfMode ? 0.05 : 0.035)
    .d3VelocityDecay(perfMode ? 0.55 : 0.45)
    .warmupTicks(perfMode ? 40 : 100)
    .cooldownTime(perfMode ? 1500 : 3000)
    .onNodeClick((node: any) => {
      const orig = nodeIndex.get(node.id)
      if (orig) emit('nodeClick', orig)
    })
    .onNodeDrag(() => {
      // During drag, force-graph reheats alpha to 0.3 which makes ALL
      // forces (charge, collision, cluster) push connected nodes around.
      // Crank velocity decay to ~0.9 so non-dragged nodes barely move.
      graph.d3VelocityDecay(0.9)
    })
    .onNodeDragEnd(() => {
      // Restore normal damping
      graph.d3VelocityDecay(perfMode ? 0.55 : 0.45)
    })
    .onLinkHover((link: any) => {
      if (link) {
        const srcId = typeof link.source === 'object' ? link.source.id : link.source
        const tgtId = typeof link.target === 'object' ? link.target.id : link.target
        hoveredEdge.value = edgeIndex.get(`${srcId}|${tgtId}|${link._type}`) ?? null
      } else {
        hoveredEdge.value = null
      }
    })
    .onNodeHover((node: any) => {
      if (containerRef.value) {
        containerRef.value.style.cursor = node ? 'pointer' : 'default'
      }
      if (node) {
        hoveredNode.value = nodeIndex.get(node.id) ?? null
        hoveredDegree.value = degrees[node.id] || 0
      } else {
        hoveredNode.value = null
        hoveredDegree.value = 0
      }
      // Force link visuals to re-evaluate so hover-focus dimming/boost
      // applies even after the physics cooldown has stopped rendering.
      // Throttled to one RAF — was previously called synchronously on every
      // mouse-move over a node, which triggered a full repaint per event.
      if (!hoverRafPending) {
        hoverRafPending = true
        requestAnimationFrame(() => {
          hoverRafPending = false
          if (!graph) return
          graph.linkColor(graph.linkColor())
          graph.linkWidth(graph.linkWidth())
          graph.linkLineDash(graph.linkLineDash())
        })
      }
    })
    .graphData((() => {
      const nodes = props.nodes ?? []
      const edges = props.edges ?? []
      const nodeIds = new Set(nodes.map(n => n.id))
      return {
        nodes: nodes.map(n => {
          const copy: any = { ...n }
          // Seed sprint nodes with positions on the ring so the simulation
          // starts already visually separated (sprint clusters don't all
          // collapse into the center on first tick).
          if (n.type === 'jira_sprint' && sprintInitialPos[n.id]) {
            copy.x = sprintInitialPos[n.id]!.x
            copy.y = sprintInitialPos[n.id]!.y
          } else if (n.type === 'jira_issue' && sprintMembership[n.id]) {
            const anchor = sprintInitialPos[sprintMembership[n.id]!]
            if (anchor) {
              // Small random offset around the sprint anchor
              copy.x = anchor.x + (Math.random() - 0.5) * 80
              copy.y = anchor.y + (Math.random() - 0.5) * 80
            }
          }
          return copy
        }),
        links: edges
          .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
          .map(e => ({ source: e.source, target: e.target, _type: e.type, _weight: e.weight, _evidence: e.evidence })),
      }
    })())

  // --- Force tuning ---
  // Balanced repulsion: enough to spread nodes out, but not so much that
  // low-degree outliers fly to the edges of the canvas.
  // distanceMax caps the repulsion range — nodes in the dense center push
  // each other apart (labels stay readable) but outliers DON'T get flung
  // to the canvas edge. This is the key to balancing center density vs spread.
  graph.d3Force('charge')?.strength((node: any) => {
    const deg = degrees[node.id] || 0
    if (node.type === 'jira_sprint') return -350 - deg * 5
    if (node.type === 'area') return -220 - deg * 6
    if (node.type === 'jira_project' || node.type === 'jira_epic') return -200 - deg * 5
    if (node.type === 'tag' || node.type === 'jira_label') return -80 - deg * 3
    return -120 - deg * 4
  }).distanceMax(450)
  graph.d3Force('link')?.distance((link: any) => {
    if (link._type === 'in_sprint') return 28
    if (link._type === 'blocks' || link._type === 'depends_on') return 85
    if (link._type === 'relates_to' || link._type === 'duplicate_of') return 65
    if (link._type === 'part_of') return 55
    if (link._type === 'tagged') return 42
    if (link._type === 'has_label' || link._type === 'has_component') return 48
    if (link._type === 'assigned_to' || link._type === 'reported_by') return 55
    return 48
  })
  graph.d3Force('link')?.strength((link: any) => {
    if (link._type === 'in_sprint') return 1.0
    if (link._type === 'blocks' || link._type === 'depends_on') return 0.2
    if (link._type === 'relates_to') return 0.15
    return 0.35
  })
  graph.d3Force('center')?.strength(0.08)

  // Collision force — prevents nodes from overlapping in dense clusters.
  // Uses each node's visual radius + a small padding so labels stay readable.
  {
    // @ts-expect-error d3-force-3d has no type declarations
    const d3 = await import('d3-force-3d')
    graph.d3Force('collide', d3.forceCollide()
      .radius((node: any) => {
        const deg = degrees[node.id] || 0
        return nodeRadius(node.type, deg) + 18
      })
      .strength(0.6)
      .iterations(1)
    )
  }

  // Custom cluster force: pull each Jira issue toward its sprint's current
  // position. Combined with strong sprint-vs-sprint repulsion this produces
  // the "pęk / kontynenty" effect the user asked for.
  if (Object.keys(sprintMembership).length > 0) {
    const clusterStrength = 0.40
    graph.d3Force('sprintCluster', (alpha: number) => {
      const data = graph.graphData()
      const byId: Record<string, any> = {}
      for (const n of data.nodes) byId[n.id] = n
      for (const n of data.nodes) {
        if (n.type !== 'jira_issue') continue
        const sprintId = sprintMembership[n.id]
        if (!sprintId) continue
        const anchor = byId[sprintId]
        if (!anchor || !Number.isFinite(anchor.x) || !Number.isFinite(anchor.y)) continue
        const k = alpha * clusterStrength
        n.vx = (n.vx || 0) + (anchor.x - (n.x ?? 0)) * k
        n.vy = (n.vy || 0) + (anchor.y - (n.y ?? 0)) * k
      }
    })
  } else {
    // Clear any lingering cluster force when no sprints are present
    graph.d3Force('sprintCluster', null)
  }

  // Re-attach ResizeObserver for the new graph instance
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      if (graph && containerRef.value) {
        graph.width(containerRef.value.clientWidth)
        graph.height(containerRef.value.clientHeight)
      }
    })
    resizeObserver.observe(containerRef.value)
  }

  // Cap DPR on hi-DPI displays — big win on Retina. force-graph exposes a
  // numeric setter for the pixel ratio used by the internal canvas.
  if (perfMode && typeof (graph as any).pixelRatio === 'function') {
    try { (graph as any).pixelRatio(1.25) } catch { /* API not available in this version */ }
  }

  // Re-run linkVisibility when the user zooms (perf mode reveals/hides
  // noisy edges based on zoom level). Throttled to rAF.
  let zoomRaf = false
  graph.onZoom?.(() => {
    if (!perfMode || zoomRaf) return
    zoomRaf = true
    requestAnimationFrame(() => {
      zoomRaf = false
      graph?.linkVisibility(graph.linkVisibility())
    })
  })

  setTimeout(() => graph?.zoomToFit(600, 60), 1500)
}

// Exposed methods for parent
function zoomToFit() { graph?.zoomToFit(400, 40) }
function zoomIn()    { graph?.zoom(graph.zoom() * 1.4, 300) }
function zoomOut()   { graph?.zoom(graph.zoom() / 1.4, 300) }

defineExpose({ zoomToFit, zoomIn, zoomOut })

// Reactivity
// Shallow watch on array identity — the parent passes freshly computed
// arrays from `filteredNodes`/`filteredEdges`, so reference equality is a
// sufficient change signal. A `deep: true` watch over 2k+ edges was a
// significant hidden cost on every filter / selection change.
// Debounced one frame so rapid filter toggling coalesces into one update.
let rebuildTimer: ReturnType<typeof setTimeout> | null = null
watch(
  [() => props.nodes, () => props.edges],
  () => {
    if (rebuildTimer) clearTimeout(rebuildTimer)
    rebuildTimer = setTimeout(async () => {
      rebuildTimer = null
      await nextTick()
      buildGraph()
    }, 50)
  },
)

watch(
  () => props.highlightedNode,
  () => {
    // Refresh both nodes and edges so focus-dimming/boost applies/clears.
    graph?.nodeColor(graph.nodeColor())
    graph?.linkColor(graph.linkColor())
    graph?.linkWidth(graph.linkWidth())
    graph?.linkLineDash(graph.linkLineDash())
  },
)

watch(
  () => props.searchMatchedIds,
  () => { graph?.nodeColor(graph.nodeColor()) },
)

watch(
  () => props.glowLevel,
  () => {
    // Trigger a repaint — node and edge draw read props.glowLevel directly.
    graph?.nodeColor(graph.nodeColor())
    graph?.linkColor(graph.linkColor())
    graph?.linkWidth(graph.linkWidth())
    graph?.linkLineDash(graph.linkLineDash())
    graph?.linkDirectionalParticles(graph.linkDirectionalParticles())
    graph?.linkDirectionalArrowLength(graph.linkDirectionalArrowLength())
  },
)

function onMouseMove(e: MouseEvent) {
  if (containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    tooltipStyle.value = {
      left: `${e.clientX - rect.left + 12}px`,
      top: `${e.clientY - rect.top - 10}px`,
    }
  }
}

onMounted(async () => {
  await nextTick()
  buildGraph()

  containerRef.value?.addEventListener('mousemove', onMouseMove)

  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      if (graph && containerRef.value) {
        graph.width(containerRef.value.clientWidth)
        graph.height(containerRef.value.clientHeight)
      }
    })
    resizeObserver.observe(containerRef.value)
  }
})

onBeforeUnmount(() => {
  containerRef.value?.removeEventListener('mousemove', onMouseMove)
  resizeObserver?.disconnect()
  if (graph) {
    graph._destructor()
    graph = null
  }
})
</script>

<style scoped>
.graph-canvas {
  width: 100%;
  height: 100%;
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border-default);
}

.graph-canvas__container {
  width: 100%;
  height: 100%;
}

/* Override force-graph's injected canvas styles */
.graph-canvas__container :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.graph-canvas__controls {
  position: absolute;
  bottom: 0.75rem;
  right: 0.75rem;
  display: flex;
  gap: 0.35rem;
  z-index: 10;
}

.graph-canvas__btn {
  padding: 0.4rem 0.7rem;
  background: var(--bg-surface);
  backdrop-filter: blur(8px);
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.graph-canvas__btn:hover {
  background: var(--bg-elevated);
  color: var(--neon-cyan);
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.graph-canvas__tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 20;
  background: rgba(6, 8, 13, 0.94);
  backdrop-filter: blur(10px);
  border: 1px solid var(--neon-cyan-30);
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.75rem;
  color: var(--text-primary);
  box-shadow: 0 0 20px var(--neon-cyan-08);
}

.graph-canvas__tooltip-type {
  font-size: 0.65rem;
  color: var(--neon-cyan-60);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.graph-canvas__tooltip-degree {
  font-size: 0.6rem;
  color: var(--text-muted);
}

.graph-canvas__edge-tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 20;
  background: rgba(6, 8, 13, 0.94);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(129, 140, 248, 0.3);
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
  gap: 0.5rem;
}

.graph-canvas__edge-tooltip-type {
  font-size: 0.6rem;
  color: rgba(165, 180, 252, 0.8);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.graph-canvas__edge-tooltip-weight {
  font-size: 0.7rem;
  font-weight: 600;
  color: rgba(165, 180, 252, 1);
}

.graph-canvas__edge-tooltip-evidence {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.graph-canvas__edge-tooltip-pair {
  font-size: 0.62rem;
  color: var(--text-secondary);
}

.graph-canvas__edge-tooltip-sim {
  color: rgba(165, 180, 252, 0.7);
  margin-left: 0.3rem;
}

.graph-canvas__edge-tooltip-note {
  font-size: 0.62rem;
  color: var(--text-muted);
  font-style: italic;
}
</style>

