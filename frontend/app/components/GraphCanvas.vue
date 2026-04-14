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
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import type { GraphNode, GraphEdge } from '~/types'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightedNode?: string | null
}>()

const emit = defineEmits<{
  nodeClick: [node: GraphNode]
}>()

const containerRef = ref<HTMLElement | null>(null)
const hoveredNode = ref<GraphNode | null>(null)
const hoveredDegree = ref(0)
const tooltipStyle = ref({ left: '0px', top: '0px' })

let graph: any = null
let resizeObserver: ResizeObserver | null = null

// --- Color palette ---
const NODE_COLOR: Record<string, string> = {
  note: 'rgba(2, 254, 255, 1)',
  tag: '#34d399',
  person: '#c084fc',
  area: '#fb923c',
}

const NODE_GLOW: Record<string, string> = {
  note: 'rgba(2, 254, 255, 0.5)',
  tag: 'rgba(52, 211, 153, 0.5)',
  person: 'rgba(192, 132, 252, 0.5)',
  area: 'rgba(251, 146, 60, 0.5)',
}

const EDGE_COLOR: Record<string, string> = {
  tagged:   'rgba(52, 211, 153, 0.7)',
  part_of:  'rgba(251, 146, 60, 0.55)',
  linked:   'rgba(2, 254, 255, 0.75)',
  mentions: 'rgba(192, 132, 252, 0.7)',
  related:  'rgba(2, 254, 255, 0.65)',
  similar_to: 'rgba(156, 163, 175, 0.4)',
  temporal: 'rgba(250, 204, 21, 0.35)',
}

const EDGE_PARTICLE_COLOR: Record<string, string> = {
  tagged:   'rgba(52, 211, 153, 0.7)',
  part_of:  'rgba(251, 146, 60, 0.5)',
  linked:   'rgba(2, 254, 255, 0.8)',
  mentions: 'rgba(192, 132, 252, 0.7)',
  related:  'rgba(2, 254, 255, 0.7)',
  similar_to: 'rgba(156, 163, 175, 0.4)',
  temporal: 'rgba(250, 204, 21, 0.3)',
}

// --- Compute degree per node (for sizing) ---
function computeDegrees(): Record<string, number> {
  const deg: Record<string, number> = {}
  const nodeIds = new Set(props.nodes.map(n => n.id))
  for (const e of props.edges) {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue
    deg[e.source] = (deg[e.source] || 0) + 1
    deg[e.target] = (deg[e.target] || 0) + 1
  }
  return deg
}

function nodeRadius(type: string, degree: number): number {
  const base = type === 'area' ? 7 : type === 'person' ? 5 : type === 'note' ? 4 : 3
  return base + Math.min(degree * 0.4, 8)
}

async function buildGraph() {
  if (!containerRef.value) return
  const el = containerRef.value

  // Disconnect previous ResizeObserver before rebuilding
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  if (graph) {
    graph._destructor()
    graph = null
  }
  el.innerHTML = ''

  if (props.nodes.length === 0) return

  const { default: ForceGraph } = await import('force-graph')
  const degrees = computeDegrees()

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
      const color = NODE_COLOR[node.type] ?? '#9ca3af'
      const glow = NODE_GLOW[node.type] ?? 'rgba(156, 163, 175, 0.3)'
      const isHighlighted = props.highlightedNode === node.id
      const isHovered = hoveredNode.value?.id === node.id

      // Layer 1 — wide, faint outer halo
      const grad1 = ctx.createRadialGradient(node.x, node.y, r * 0.5, node.x, node.y, r + 14)
      grad1.addColorStop(0, glow.replace(/[\d.]+\)$/, '0.28)'))
      grad1.addColorStop(1, glow.replace(/[\d.]+\)$/, '0.0)'))
      ctx.beginPath()
      ctx.arc(node.x, node.y, r + 14, 0, 2 * Math.PI)
      ctx.fillStyle = grad1
      ctx.fill()

      // Layer 2 — mid glow
      const grad2 = ctx.createRadialGradient(node.x, node.y, r * 0.3, node.x, node.y, r + 12)
      grad2.addColorStop(0, glow.replace(/[\d.]+\)$/, '0.45)'))
      grad2.addColorStop(1, glow.replace(/[\d.]+\)$/, '0.0)'))
      ctx.beginPath()
      ctx.arc(node.x, node.y, r + 12, 0, 2 * Math.PI)
      ctx.fillStyle = grad2
      ctx.fill()

      // Layer 3 — tight inner glow ring
      const grad3 = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r + 4)
      grad3.addColorStop(0, glow.replace(/[\d.]+\)$/, '0.6)'))
      grad3.addColorStop(0.6, glow.replace(/[\d.]+\)$/, '0.35)'))
      grad3.addColorStop(1, glow.replace(/[\d.]+\)$/, '0.0)'))
      ctx.beginPath()
      ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI)
      ctx.fillStyle = grad3
      ctx.fill()

      // Shadow glow on node body
      if (isHighlighted || isHovered) {
        ctx.shadowColor = color
        ctx.shadowBlur = isHighlighted ? 50 : 36
      } else {
        ctx.shadowColor = color
        ctx.shadowBlur = 28
      }

      // Node body — radial gradient core (bright center → dim edge)
      const bodyGrad = ctx.createRadialGradient(node.x - r * 0.25, node.y - r * 0.25, 0, node.x, node.y, r)
      bodyGrad.addColorStop(0, 'rgba(255,255,255,0.55)')
      bodyGrad.addColorStop(0.4, color)
      bodyGrad.addColorStop(1, glow.replace(/[\d.]+\)$/, '0.8)'))
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = bodyGrad
      ctx.fill()

      // Bright edge ring
      ctx.strokeStyle = 'rgba(255,255,255,0.25)'
      ctx.lineWidth = 0.6
      ctx.stroke()

      ctx.shadowBlur = 0

      // Label logic: always show for area, show for high-degree nodes, else only on zoom
      const showLabel =
        node.type === 'area' ||
        deg >= 4 ||
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
      const type = link._type || 'tagged'
      return EDGE_COLOR[type] ?? 'rgba(100, 160, 220, 0.15)'
    })
    .linkWidth((link: any) => {
      const type = link._type || 'tagged'
      if (type === 'linked' || type === 'related') return 3.5
      if (type === 'part_of') return 1.2
      if (type === 'similar_to' || type === 'temporal') return 1.0
      return 2
    })
    .linkLineDash((link: any) => {
      if (link._type === 'part_of') return [2, 2]
      if (link._type === 'similar_to') return [3, 3]
      if (link._type === 'temporal') return [1, 3]
      return []
    })
    .linkDirectionalArrowLength((link: any) => {
      return link._type === 'linked' || link._type === 'related' ? 4 : 0
    })
    .linkDirectionalArrowRelPos(0.85)
    .linkDirectionalParticles((link: any) => {
      // More particles = more life! Different edge types get different densities
      if (link._type === 'linked') return 3
      if (link._type === 'related') return 2
      if (link._type === 'tagged') return 2
      if (link._type === 'mentions') return 2
      if (link._type === 'part_of') return 1
      return 1
    })
    .linkDirectionalParticleWidth((link: any) => {
      if (link._type === 'linked' || link._type === 'related') return 2.2
      if (link._type === 'tagged') return 1.8
      return 1.4
    })
    .linkDirectionalParticleSpeed((link: any) => {
      // Varied speeds make the graph feel organic and alive
      if (link._type === 'linked') return 0.006 + Math.random() * 0.004
      if (link._type === 'related') return 0.005 + Math.random() * 0.003
      if (link._type === 'tagged') return 0.003 + Math.random() * 0.002
      if (link._type === 'mentions') return 0.004 + Math.random() * 0.003
      if (link._type === 'part_of') return 0.002 + Math.random() * 0.002
      if (link._type === 'similar_to') return 0.001 + Math.random() * 0.001
      if (link._type === 'temporal') return 0.002 + Math.random() * 0.001
      return 0.003 + Math.random() * 0.002
    })
    .linkDirectionalParticleColor((link: any) => {
      return EDGE_PARTICLE_COLOR[link._type] ?? 'rgba(100, 180, 255, 0.4)'
    })
    .linkCurvature((link: any) => {
      // Slight curve to avoid overlapping straight lines
      return link._type === 'part_of' ? 0.15 : 0
    })
    // --- Interaction ---
    .enableNodeDrag(true)
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    .d3AlphaDecay(0.02)
    .d3VelocityDecay(0.3)
    .warmupTicks(80)
    .cooldownTime(4000)
    .onNodeClick((node: any) => {
      const orig = props.nodes.find(n => n.id === node.id)
      if (orig) emit('nodeClick', orig)
    })
    .onNodeHover((node: any) => {
      if (containerRef.value) {
        containerRef.value.style.cursor = node ? 'pointer' : 'default'
      }
      if (node) {
        hoveredNode.value = props.nodes.find(n => n.id === node.id) ?? null
        hoveredDegree.value = degrees[node.id] || 0
      } else {
        hoveredNode.value = null
        hoveredDegree.value = 0
      }
    })
    .graphData((() => {
      const nodeIds = new Set(props.nodes.map(n => n.id))
      return {
        nodes: props.nodes.map(n => ({ ...n })),
        links: props.edges
          .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
          .map(e => ({ source: e.source, target: e.target, _type: e.type })),
      }
    })())

  // --- Force tuning ---
  // Areas strongly repel, tags weakly repel: tiered charge
  graph.d3Force('charge')?.strength((node: any) => {
    const deg = degrees[node.id] || 0
    if (node.type === 'area') return -200 - deg * 10
    if (node.type === 'tag') return -30 - deg * 3
    return -60 - deg * 5
  })
  graph.d3Force('link')?.distance((link: any) => {
    if (link._type === 'part_of') return 50
    if (link._type === 'tagged') return 35
    return 45
  })
  graph.d3Force('center')?.strength(0.05)

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

  setTimeout(() => graph?.zoomToFit(600, 60), 1500)
}

// Exposed methods for parent
function zoomToFit() { graph?.zoomToFit(400, 40) }
function zoomIn()    { graph?.zoom(graph.zoom() * 1.4, 300) }
function zoomOut()   { graph?.zoom(graph.zoom() / 1.4, 300) }

defineExpose({ zoomToFit, zoomIn, zoomOut })

// Reactivity
watch(
  () => [props.nodes, props.edges],
  async () => {
    await nextTick()
    buildGraph()
  },
  { deep: true },
)

watch(
  () => props.highlightedNode,
  () => { graph?.nodeColor(graph.nodeColor()) },
)

onMounted(async () => {
  await nextTick()
  buildGraph()

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
</style>

