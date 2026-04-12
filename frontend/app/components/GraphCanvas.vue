<template>
  <div class="graph-canvas" ref="canvasRef">
    <svg v-if="nodes.length" class="graph-canvas__svg" :viewBox="viewBox">
      <g :transform="`translate(${pan.x},${pan.y}) scale(${zoom})`">
        <line
          v-for="(edge, i) in edges"
          :key="'e' + i"
          class="graph-canvas__edge"
          :x1="nodePositions[edge.source]?.x ?? 0"
          :y1="nodePositions[edge.source]?.y ?? 0"
          :x2="nodePositions[edge.target]?.x ?? 0"
          :y2="nodePositions[edge.target]?.y ?? 0"
        />
        <g
          v-for="node in nodes"
          :key="node.id"
          class="graph-canvas__node"
          :transform="`translate(${nodePositions[node.id]?.x ?? 0},${nodePositions[node.id]?.y ?? 0})`"
          @click="$emit('nodeClick', node)"
        >
          <circle
            r="8"
            :class="'graph-canvas__dot graph-canvas__dot--' + node.type"
          />
          <text dy="20" text-anchor="middle" class="graph-canvas__label">{{ node.label }}</text>
        </g>
      </g>
    </svg>
    <p v-else class="graph-canvas__empty">No graph — create notes first</p>
  </div>
</template>

<script setup lang="ts">
import type { GraphNode, GraphEdge } from '~/types'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
  highlightedNode?: string | null
}>()

defineEmits<{
  nodeClick: [node: GraphNode]
}>()

const canvasRef = ref<HTMLElement | null>(null)
const zoom = ref(1)
const pan = reactive({ x: 300, y: 200 })

const viewBox = computed(() => `0 0 600 400`)

// Simple circular layout for nodes
const nodePositions = computed(() => {
  const positions: Record<string, { x: number; y: number }> = {}
  const count = props.nodes.length
  if (count === 0) return positions

  const cx = 300
  const cy = 200
  const radius = Math.min(200, count * 20)

  props.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / count
    positions[node.id] = {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    }
  })
  return positions
})

function zoomIn(): void {
  zoom.value = Math.min(zoom.value * 1.2, 3)
}

function zoomOut(): void {
  zoom.value = Math.max(zoom.value / 1.2, 0.3)
}

function fitToView(): void {
  zoom.value = 1
  pan.x = 300
  pan.y = 200
}

defineExpose({ zoomIn, zoomOut, fitToView })
</script>

<style scoped>
.graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
}

.graph-canvas__svg {
  width: 100%;
  height: 100%;
}

.graph-canvas__edge {
  stroke: #555;
  stroke-width: 1;
}

.graph-canvas__node {
  cursor: pointer;
}

.graph-canvas__dot {
  fill: #4a9eff;
}

.graph-canvas__dot--tag {
  fill: #4caf50;
}

.graph-canvas__dot--person {
  fill: #ff9800;
}

.graph-canvas__dot--area {
  fill: #9c27b0;
}

.graph-canvas__dot--topic {
  fill: #e91e63;
}

.graph-canvas__label {
  font-size: 10px;
  fill: #ccc;
}

.graph-canvas__empty {
  text-align: center;
  color: #666;
  padding-top: 4rem;
}
</style>
