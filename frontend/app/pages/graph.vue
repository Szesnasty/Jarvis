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

    <GraphFilterBar
      :filters="filters"
      :orphan-count="orphans.length"
      :all-nodes="graph.nodes"
      @update:filters="setFilters"
    />

    <!-- Orphan banner -->
    <div v-if="orphans.length > 0 && !filters.showOrphans" class="graph-view__orphan-banner">
      You have {{ orphans.length }} unconnected note{{ orphans.length > 1 ? 's' : '' }}.
      <button class="graph-view__orphan-link" @click="setFilters({ ...filters, showOrphans: true })">View them</button>
    </div>

    <div class="graph-view__main">
      <div class="graph-view__canvas">
        <GraphCanvas
          ref="canvasRef"
          :nodes="filteredNodes"
          :edges="filteredEdges"
          :highlighted-node="highlightedNodeId"
          :search-matched-ids="searchMatchedNodeIds"
          :glow-level="filters.glowLevel"
          @node-click="handleNodeClick"
        />
      </div>
      <GraphNodePreview
        v-if="selectedNode"
        :node="selectedNode"
        :similar-edges="selectedSimilarEdges"
        @close="selectNode(null)"
        @navigate-node="handleNavigateNode"
        @ask-about="handleAskAbout"
        @open-in-memory="handleOpenInMemory"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import type { GraphNode } from '~/types'
import { useGraph } from '~/composables/useGraph'
import { useIngestStatus } from '~/composables/useIngestStatus'
import GraphCanvas from '~/components/GraphCanvas.vue'
import GraphNodePreview from '~/components/GraphNodePreview.vue'
import GraphFilterBar from '~/components/GraphFilterBar.vue'

const {
  graph, stats, selectedNode, orphans, filters,
  filteredNodes, filteredEdges, highlightedNodeId, searchMatchedNodeIds, selectedSimilarEdges,
  loadGraph, rebuildGraph, selectNode, setFilters,
} = useGraph()

const canvasRef = ref<InstanceType<typeof GraphCanvas> | null>(null)
const ingest = useIngestStatus()

// Auto-reload graph when a graph_rebuild job transitions from running → done.
// We track whether a rebuild was active; when active_count drops to 0 after
// having a rebuild job, we reload the graph data automatically.
let rebuildWasActive = false
watch(
  () => ingest.active.value.some((j: any) => j.kind === 'graph_rebuild'),
  (isActive: boolean) => {
    if (isActive) {
      rebuildWasActive = true
    } else if (rebuildWasActive) {
      rebuildWasActive = false
      loadGraph()
    }
  },
)

function handleNodeClick(node: GraphNode): void {
  selectNode(node)
}

function handleNavigateNode(nodeId: string): void {
  const node = filteredNodes.value.find(n => n.id === nodeId)
  if (node) selectNode(node)
}

function handleAskAbout(nodeId: string): void {
  navigateTo(`/main?graph_scope=${encodeURIComponent(nodeId)}`)
}

function handleOpenInMemory(path: string): void {
  navigateTo(`/memory?note=${encodeURIComponent(path)}`)
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
  canvasRef.value?.zoomToFit()
}

// Reload graph when memory changes from chat (write_note, append_note, etc.)
function handleMemoryChanged(): void {
  loadGraph()
}

onMounted(async () => {
  await loadGraph()
  window.addEventListener('jarvis:memory-changed', handleMemoryChanged)
})

onUnmounted(() => {
  window.removeEventListener('jarvis:memory-changed', handleMemoryChanged)
})
</script>

<style scoped>
.graph-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-deep);
}

.graph-view__toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.6rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-base);
}

.graph-view__title {
  font-size: 0.95rem;
  margin: 0;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.graph-view__controls {
  display: flex;
  gap: 0.35rem;
}

.graph-view__btn {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  padding: 0.25rem 0.65rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.graph-view__btn:hover {
  color: var(--neon-cyan);
  border-color: var(--neon-cyan-30);
  background: var(--bg-elevated);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}

.graph-view__stats {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: auto;
}

.graph-view__orphan-banner {
  padding: 0.4rem 1.25rem;
  background: rgba(251, 113, 133, 0.06);
  border-bottom: 1px solid rgba(251, 113, 133, 0.15);
  font-size: 0.75rem;
  color: rgb(251, 113, 133);
}

.graph-view__orphan-link {
  background: none;
  border: none;
  color: rgb(251, 113, 133);
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 0;
  margin-left: 0.3rem;
}

.graph-view__main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.graph-view__canvas {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
</style>
