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
    // Folder `area` nodes are pure structural noise — hide by default; user can re-enable in the legend.
    hiddenTypes: new Set<string>(['area']),
    timeRange: 'all',
    showOrphans: false,
    searchText: '',
    selectedSprints: new Set<string>(),
    glowLevel: 'normal',
    hideHubs: false,
    hubThreshold: 50,
    bridgesOnly: false,
  })

  const { fetchGraph, fetchGraphStats, fetchGraphNeighbors, fetchOrphans, rebuildGraph: apiRebuild } = useApi()

  // When sprints are selected, compute the subgraph membership.
  // - Issues kept: those connected via `in_sprint` edges to any selected sprint.
  // - Non-issue / non-sprint nodes kept: those connected to any kept issue.
  // - Sprint nodes kept: only the selected ones.
  const sprintSubgraphIds = computed(() => {
    const selected = filters.value.selectedSprints
    if (!selected || selected.size === 0) return null
    const issueIds = new Set<string>()
    for (const e of graph.value.edges) {
      if (e.type !== 'in_sprint') continue
      // in_sprint edges: issue -> sprint (source is issue, target is sprint)
      if (selected.has(e.target)) issueIds.add(e.source)
      else if (selected.has(e.source)) issueIds.add(e.target)
    }
    const keep = new Set<string>(issueIds)
    for (const id of selected) keep.add(id)
    // Pull in directly connected non-issue / non-sprint nodes (labels, epics, people, etc.)
    const nodeById = new Map(graph.value.nodes.map(n => [n.id, n]))
    for (const e of graph.value.edges) {
      const src = nodeById.get(e.source)
      const tgt = nodeById.get(e.target)
      if (!src || !tgt) continue
      if (issueIds.has(e.source) && tgt.type !== 'jira_sprint') keep.add(e.target)
      if (issueIds.has(e.target) && src.type !== 'jira_sprint') keep.add(e.source)
    }
    return keep
  })

  // Per-node edge degree across the full graph — used for hub suppression.
  const nodeDegree = computed(() => {
    const deg = new Map<string, number>()
    for (const e of graph.value.edges) {
      deg.set(e.source, (deg.get(e.source) ?? 0) + 1)
      deg.set(e.target, (deg.get(e.target) ?? 0) + 1)
    }
    return deg
  })

  // Entity-type nodes that bridge ≥2 distinct notes. Single-source entities (one paper → hundreds of
  // extracted people/orgs) are pure noise and dominate the canvas as a star pattern.
  const ENTITY_TYPES = new Set([
    'person', 'org', 'project', 'place', 'source', 'tag', 'batch',
    'jira_person', 'jira_label', 'jira_component',
  ])
  const bridgeEntityIds = computed(() => {
    const noteCount = new Map<string, Set<string>>()
    const isNote = (id: string) => id.startsWith('note:')
    for (const e of graph.value.edges) {
      const noteSide = isNote(e.source) ? e.source : isNote(e.target) ? e.target : null
      const otherSide = isNote(e.source) ? e.target : isNote(e.target) ? e.source : null
      if (!noteSide || !otherSide || otherSide === noteSide) continue
      let set = noteCount.get(otherSide)
      if (!set) { set = new Set(); noteCount.set(otherSide, set) }
      set.add(noteSide)
    }
    const bridges = new Set<string>()
    for (const [id, notes] of noteCount.entries()) {
      if (notes.size >= 2) bridges.add(id)
    }
    return bridges
  })

  const filteredNodes = computed(() => {
    let nodes = graph.value.nodes
    const sprintKeep = sprintSubgraphIds.value
    if (sprintKeep) {
      nodes = nodes.filter(n => {
        // Always drop non-selected sprint nodes when sprint filter is active.
        if (n.type === 'jira_sprint') return filters.value.selectedSprints.has(n.id)
        return sprintKeep.has(n.id)
      })
    }
    if (filters.value.hiddenTypes.size > 0) {
      nodes = nodes.filter(n => !filters.value.hiddenTypes.has(n.type))
    }
    if (filters.value.hideHubs) {
      const threshold = filters.value.hubThreshold
      const deg = nodeDegree.value
      nodes = nodes.filter(n => (deg.get(n.id) ?? 0) <= threshold)
    }
    if (filters.value.bridgesOnly) {
      const bridges = bridgeEntityIds.value
      nodes = nodes.filter(n => !ENTITY_TYPES.has(n.type) || bridges.has(n.id))
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
