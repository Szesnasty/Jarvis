import type { GraphData, GraphNode, GraphStats } from '~/types'
import { useApi } from '~/composables/useApi'

export function useGraph() {
  const graph = ref<GraphData>({ nodes: [], edges: [] })
  const stats = ref<GraphStats>({ node_count: 0, edge_count: 0, top_connected: [] })
  const selectedNode = ref<GraphNode | null>(null)
  const isLoading = ref(false)

  const { fetchGraph, fetchGraphStats, fetchGraphNeighbors, rebuildGraph: apiRebuild } = useApi()

  async function loadGraph(): Promise<void> {
    isLoading.value = true
    try {
      graph.value = await fetchGraph()
      stats.value = await fetchGraphStats()
    } finally {
      isLoading.value = false
    }
  }

  async function rebuildGraph(): Promise<void> {
    isLoading.value = true
    try {
      stats.value = await apiRebuild()
      graph.value = await fetchGraph()
    } finally {
      isLoading.value = false
    }
  }

  async function queryNeighbors(nodeId: string, depth = 1): Promise<GraphNode[]> {
    return await fetchGraphNeighbors(nodeId, depth)
  }

  function selectNode(node: GraphNode | null): void {
    selectedNode.value = node
  }

  return { graph, stats, selectedNode, isLoading, loadGraph, rebuildGraph, queryNeighbors, selectNode }
}
