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
    <div class="graph-canvas__legend">
      <span class="graph-canvas__legend-item"><i style="background:#60a5fa"></i> note</span>
      <span class="graph-canvas__legend-item"><i style="background:#34d399"></i> tag</span>
      <span class="graph-canvas__legend-item"><i style="background:#c084fc"></i> person</span>
      <span class="graph-canvas__legend-item"><i style="background:#fb923c"></i> area</span>
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
  note: '#60a5fa',
  tag: '#34d399',
  person: '#c084fc',
  area: '#fb923c',
}

const EDGE_COLOR: Record<string, string> = {
  tagged:   'rgba(52, 211, 153, 0.35)',   // green — tag links
  part_of:  'rgba(251, 146, 60, 0.25)',   // orange — folder membership
  linked:   'rgba(167, 139, 250, 0.45)',  // purple — wiki links
  mentions: 'rgba(192, 132, 252, 0.4)',   // purple — people
  related:  'rgba(96, 165, 250, 0.4)',    // blue — explicit related
}

const EDGE_PARTICLE_COLOR: Record<string, string> = {
  tagged:   'rgba(52, 211, 153, 0.6)',
  part_of:  'rgba(251, 146, 60, 0.4)',
  linked:   'rgba(167, 139, 250, 0.7)',
  mentions: 'rgba(192, 132, 252, 0.6)',
  related:  'rgba(96, 165, 250, 0.6)',
}

// --- Compute degree per node (for sizing) ---
function computeDegrees(): Record<string, number> {
  const deg: Record<string, number> = {}
  for (const e of props.edges) {
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

  if (graph) {
    graph._destructor()
    graph = null
  }
  el.innerHTML = ''

  if (props.nodes.length === 0) return

  const { default: ForceGraph } = await import('force-graph')
  const degrees = computeDegrees()

  graph = new ForceGraph(el)
    .backgroundColor('#0f172a')
    .width(el.clientWidth)
    .height(el.clientHeight)
    .nodeId('id')
    .nodeLabel('')
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const deg = degrees[node.id] || 0
      const r = nodeRadius(node.type, deg)
      const color = NODE_COLOR[node.type] ?? '#9ca3af'
      const isHighlighted = props.highlightedNode === node.id
      const isHovered = hoveredNode.value?.id === node.id

      // Outer glow for highlighted / hovered
      if (isHighlighted || isHovered) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, r + 4, 0, 2 * Math.PI)
        ctx.fillStyle = color.replace(')', ', 0.15)').replace('rgb', 'rgba')
        ctx.fill()

        ctx.shadowColor = color
        ctx.shadowBlur = isHighlighted ? 20 : 12
      }

      // Node body
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()

      // Subtle border for areas
      if (node.type === 'area') {
        ctx.strokeStyle = 'rgba(255,255,255,0.3)'
        ctx.lineWidth = 0.5
        ctx.stroke()
      }

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
      if (type === 'linked' || type === 'related') return 1.8
      if (type === 'part_of') return 0.6
      return 1
    })
    .linkLineDash((link: any) => {
      return link._type === 'part_of' ? [2, 2] : []
    })
    .linkDirectionalArrowLength((link: any) => {
      return link._type === 'linked' || link._type === 'related' ? 4 : 0
    })
    .linkDirectionalArrowRelPos(0.85)
    .linkDirectionalParticles((link: any) => {
      return link._type === 'tagged' || link._type === 'linked' ? 1 : 0
    })
    .linkDirectionalParticleWidth(1.2)
    .linkDirectionalParticleSpeed(0.003)
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
    .graphData({
      nodes: props.nodes.map(n => ({ ...n })),
      links: props.edges.map(e => ({ source: e.source, target: e.target, _type: e.type })),
    })

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
  border-radius: 8px;
  overflow: hidden;
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
  background: rgba(30, 41, 59, 0.85);
  backdrop-filter: blur(6px);
  color: #94a3b8;
  border: 1px solid rgba(100, 116, 139, 0.3);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.15s;
}

.graph-canvas__btn:hover {
  background: rgba(51, 65, 85, 0.9);
  color: #e2e8f0;
}

.graph-canvas__tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 20;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(100, 160, 220, 0.3);
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.75rem;
  color: #e2e8f0;
}

.graph-canvas__tooltip-type {
  font-size: 0.65rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.graph-canvas__tooltip-degree {
  font-size: 0.6rem;
  color: #475569;
}

.graph-canvas__legend {
  position: absolute;
  top: 0.6rem;
  left: 0.6rem;
  display: flex;
  gap: 0.6rem;
  z-index: 10;
  font-size: 0.65rem;
  color: #64748b;
}

.graph-canvas__legend-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.graph-canvas__legend-item i {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>

