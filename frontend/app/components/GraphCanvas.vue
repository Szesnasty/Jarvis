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
      <span class="graph-canvas__tooltip-type">{{ hoveredNode.type }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
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
const tooltipStyle = ref({ left: '0px', top: '0px' })

let graph: any = null
let resizeObserver: ResizeObserver | null = null

const COLOR_MAP: Record<string, string> = {
  note: '#60a5fa',
  tag: '#34d399',
  person: '#c084fc',
  area: '#fb923c',
}

const SIZE_MAP: Record<string, number> = {
  note: 5,
  tag: 3,
  person: 6,
  area: 8,
}

async function buildGraph() {
  if (!containerRef.value) return
  const el = containerRef.value

  // Destroy previous instance
  if (graph) {
    graph._destructor()
    graph = null
  }
  el.innerHTML = ''

  if (props.nodes.length === 0) return

  // Dynamic import — only runs on client
  const { default: ForceGraph } = await import('force-graph')

  graph = new ForceGraph(el)
    .backgroundColor('#0f172a')
    .width(el.clientWidth)
    .height(el.clientHeight)
    .nodeId('id')
    .nodeColor((n: any) => COLOR_MAP[n.type] ?? '#9ca3af')
    .nodeLabel('')
    .nodeRelSize(1)
    .nodeCanvasObjectMode(() => 'replace')
    .nodeCanvasObject((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const r = SIZE_MAP[node.type] ?? 4
      const isHighlighted = props.highlightedNode === node.id

      // Glow effect
      if (isHighlighted) {
        ctx.shadowColor = COLOR_MAP[node.type] ?? '#60a5fa'
        ctx.shadowBlur = 15
      }

      // Node circle
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = COLOR_MAP[node.type] ?? '#9ca3af'
      ctx.fill()
      ctx.shadowBlur = 0

      // Label (only when zoomed enough)
      if (globalScale > 0.8) {
        const fontSize = Math.min(12 / globalScale, 5)
        ctx.font = `${fontSize}px Sans-Serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        ctx.fillStyle = 'rgba(255, 255, 255, 0.7)'
        ctx.fillText(node.label, node.x, node.y + r + 2)
      }
    })
    .nodePointerAreaPaint((node: any, color: string, ctx: CanvasRenderingContext2D) => {
      const r = (SIZE_MAP[node.type] ?? 4) + 3
      ctx.beginPath()
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
    })
    .linkColor(() => 'rgba(100, 160, 220, 0.15)')
    .linkWidth(1)
    .linkDirectionalParticles(2)
    .linkDirectionalParticleWidth(1.5)
    .linkDirectionalParticleSpeed(0.004)
    .linkDirectionalParticleColor(() => 'rgba(100, 180, 255, 0.4)')
    .enableNodeDrag(true)
    .enableZoomInteraction(true)
    .enablePanInteraction(true)
    .d3AlphaDecay(0.02)
    .d3VelocityDecay(0.3)
    .warmupTicks(50)
    .cooldownTime(3000)
    .onNodeClick((node: any) => {
      const orig = props.nodes.find(n => n.id === node.id)
      if (orig) emit('nodeClick', orig)
    })
    .onNodeHover((node: any) => {
      if (containerRef.value) {
        containerRef.value.style.cursor = node ? 'pointer' : 'default'
      }
      hoveredNode.value = node
        ? (props.nodes.find(n => n.id === node.id) ?? null)
        : null
    })
    .graphData({
      nodes: props.nodes.map(n => ({ ...n })),
      links: props.edges.map(e => ({ source: e.source, target: e.target })),
    })

  // Tune forces after instantiation
  graph.d3Force('charge')?.strength(-80)
  graph.d3Force('link')?.distance(30)
  graph.d3Force('center')?.strength(0.1)

  // Initial zoom-to-fit after layout settles
  setTimeout(() => graph?.zoomToFit(600, 60), 1200)
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
    if (graph && props.nodes.length > 0) {
      graph.graphData({
        nodes: props.nodes.map(n => ({ ...n })),
        links: props.edges.map(e => ({ source: e.source, target: e.target })),
      })
      setTimeout(() => graph?.zoomToFit(600, 60), 1200)
    } else {
      buildGraph()
    }
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

  // Responsive sizing
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

// Track mouse for tooltip
function handleMouseMove(e: MouseEvent) {
  tooltipStyle.value = { left: `${e.offsetX + 14}px`, top: `${e.offsetY - 10}px` }
}
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
</style>

