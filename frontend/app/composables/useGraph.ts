import type { GraphData, GraphEdge, GraphNode, GraphOrphan, GraphStats } from '~/types'
import type { GraphFilters } from '~/components/GraphFilterBar.vue'
import { useApi } from '~/composables/useApi'

function getTimeCutoff(range: string): string {
  const now = new Date()
  const days = range === '7d' ? 7 : range === '30d' ? 30 : range === '90d' ? 90 : 0
  if (!days) return ''
  now.setDate(now.getDate() - days)
  return now.toISOString()
}

export function useGraph() {
  const graph = ref<GraphData>({ nodes: [], edges: [] })
  const stats = ref<GraphStats>({ node_count: 0, edge_count: 0, top_connected: [] })
  const selectedNode = ref<GraphNode | null>(null)
  const orphans = ref<GraphOrphan[]>([])
  const isLoading = ref(false)

  const filters = ref<GraphFilters>({
    hiddenTypes: new Set<string>(),
    timeRange: 'all',
    showOrphans: false,
    searchText: '',
  })

  const { fetchGraph, fetchGraphStats, fetchGraphNeighbors, fetchOrphans, rebuildGraph: apiRebuild } = useApi()

  const filteredNodes = computed(() => {
    let nodes = graph.value.nodes
    if (filters.value.hiddenTypes.size > 0) {
      nodes = nodes.filter(n => !filters.value.hiddenTypes.has(n.type))
    }
    // Search text does NOT filter nodes — it highlights them via searchMatchedNodeIds
    return nodes
  })

  const searchMatchedNodeIds = computed(() => {
    if (!filters.value.searchText) return new Set<string>()
    const q = filters.value.searchText.toLowerCase()
    return new Set(
      graph.value.nodes
        .filter(n => n.label.toLowerCase().includes(q))
        .map(n => n.id)
    )
  })

  const filteredEdges = computed(() => {
    const nodeIds = new Set(filteredNodes.value.map(n => n.id))
    return graph.value.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
  })

  const highlightedNodeId = computed(() => {
    if (searchMatchedNodeIds.value.size === 1) {
      return [...searchMatchedNodeIds.value][0]
    }
    return selectedNode.value?.id ?? null
  })

  const selectedSimilarEdges = computed(() => {
    if (!selectedNode.value) return []
    const id = selectedNode.value.id
    return filteredEdges.value.filter(
      e => e.type === 'similar_to' && (e.source === id || e.target === id)
    )
  })

  async function loadGraph(): Promise<void> {
    isLoading.value = true
    try {
      const [g, s, o] = await Promise.all([fetchGraph(), fetchGraphStats(), fetchOrphans()])
      graph.value = g
      stats.value = s
      orphans.value = o
    } finally {
      isLoading.value = false
    }
  }

  async function rebuildGraph(): Promise<void> {
    isLoading.value = true
    try {
      stats.value = await apiRebuild()
      const [g, o] = await Promise.all([fetchGraph(), fetchOrphans()])
      graph.value = g
      orphans.value = o
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

  function setFilters(f: GraphFilters): void {
    filters.value = f
  }

  return {
    graph, stats, selectedNode, orphans, isLoading, filters,
    filteredNodes, filteredEdges, highlightedNodeId, searchMatchedNodeIds, selectedSimilarEdges,
    loadGraph, rebuildGraph, queryNeighbors, selectNode, setFilters,
  }
}
