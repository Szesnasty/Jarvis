<template>
  <div class="graph-view">
    <div class="graph-view__toolbar">
      <h2 class="graph-view__title">Knowledge Graph</h2>
      <div class="graph-view__controls">
        <button class="graph-view__btn" @click="handleRebuild">Rebuild</button>
        <button class="graph-view__btn" @click="handleZoomIn">+</button>
        <button class="graph-view__btn" @click="handleZoomOut">-</button>
        <button class="graph-view__btn" @click="handleFit">Fit</button>
      </div>
      <span class="graph-view__stats">{{ stats.node_count }} nodes · {{ stats.edge_count }} edges</span>
    </div>
    <div class="graph-view__main">
      <GraphCanvas
        ref="canvasRef"
        :nodes="graph.nodes"
        :edges="graph.edges"
        :highlighted-node="selectedNode?.id ?? null"
        @node-click="handleNodeClick"
      />
      <aside v-if="selectedNode" class="graph-view__preview">
        <h3 class="graph-view__preview-title">{{ selectedNode.label }}</h3>
        <p class="graph-view__preview-type">{{ selectedNode.type }}</p>
        <p v-if="selectedNode.folder" class="graph-view__preview-folder">{{ selectedNode.folder }}</p>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { GraphNode } from '~/types'
import { useGraph } from '~/composables/useGraph'

const { graph, stats, selectedNode, loadGraph, rebuildGraph, selectNode } = useGraph()

const canvasRef = ref<InstanceType<typeof import('~/components/GraphCanvas.vue').default> | null>(null)

function handleNodeClick(node: GraphNode): void {
  selectNode(node)
}

async function handleRebuild(): Promise<void> {
  await rebuildGraph()
}

function handleZoomIn(): void {
  canvasRef.value?.zoomIn()
}

function handleZoomOut(): void {
  canvasRef.value?.zoomOut()
}

function handleFit(): void {
  canvasRef.value?.fitToView()
}

onMounted(() => {
  loadGraph()
})
</script>

<style scoped>
.graph-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.graph-view__toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #333;
}

.graph-view__title {
  font-size: 1rem;
  margin: 0;
  color: #eee;
}

.graph-view__controls {
  display: flex;
  gap: 0.3rem;
}

.graph-view__btn {
  background: #2a2a2a;
  border: 1px solid #555;
  color: #ccc;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}

.graph-view__stats {
  font-size: 0.75rem;
  color: #888;
  margin-left: auto;
}

.graph-view__main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.graph-view__preview {
  width: 250px;
  border-left: 1px solid #333;
  padding: 1rem;
}

.graph-view__preview-title {
  font-size: 0.9rem;
  margin: 0 0 0.3rem;
  color: #eee;
}

.graph-view__preview-type {
  font-size: 0.75rem;
  color: #888;
  text-transform: uppercase;
}

.graph-view__preview-folder {
  font-size: 0.75rem;
  color: #666;
}
</style>
