import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetchGraph = vi.fn()
const mockFetchGraphStats = vi.fn()
const mockFetchGraphNeighbors = vi.fn()
const mockRebuildGraph = vi.fn()

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    fetchGraph: mockFetchGraph,
    fetchGraphStats: mockFetchGraphStats,
    fetchGraphNeighbors: mockFetchGraphNeighbors,
    rebuildGraph: mockRebuildGraph,
  }),
}))

import { useGraph } from '~/composables/useGraph'

const MOCK_GRAPH = {
  nodes: [
    { id: 'note:test.md', type: 'note', label: 'Test', folder: '' },
    { id: 'tag:python', type: 'tag', label: 'python', folder: '' },
  ],
  edges: [
    { source: 'note:test.md', target: 'tag:python', type: 'tagged' },
  ],
}

const MOCK_STATS = { node_count: 2, edge_count: 1, top_connected: [] }

describe('useGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchGraph.mockResolvedValue(MOCK_GRAPH)
    mockFetchGraphStats.mockResolvedValue(MOCK_STATS)
  })

  it('loadGraph fetches from API', async () => {
    const { graph, loadGraph } = useGraph()
    await loadGraph()
    expect(mockFetchGraph).toHaveBeenCalledOnce()
    expect(graph.value.nodes).toHaveLength(2)
  })

  it('rebuildGraph calls POST rebuild', async () => {
    mockRebuildGraph.mockResolvedValue(MOCK_STATS)
    const { rebuildGraph } = useGraph()
    await rebuildGraph()
    expect(mockRebuildGraph).toHaveBeenCalledOnce()
  })

  it('selectedNode reactive ref updates on select', () => {
    const { selectedNode, selectNode } = useGraph()
    expect(selectedNode.value).toBeNull()
    selectNode({ id: 'note:test.md', type: 'note', label: 'Test', folder: '' })
    expect(selectedNode.value?.id).toBe('note:test.md')
  })

  it('queryNeighbors returns filtered data', async () => {
    mockFetchGraphNeighbors.mockResolvedValue([{ id: 'tag:python', type: 'tag', label: 'python', folder: '' }])
    const { queryNeighbors } = useGraph()
    const result = await queryNeighbors('note:test.md')
    expect(mockFetchGraphNeighbors).toHaveBeenCalledWith('note:test.md', 1)
    expect(result).toHaveLength(1)
  })

  it('loading state during fetch', async () => {
    let resolveGraph!: (v: typeof MOCK_GRAPH) => void
    mockFetchGraph.mockReturnValue(new Promise(r => { resolveGraph = r }))

    const { isLoading, loadGraph } = useGraph()
    expect(isLoading.value).toBe(false)

    const promise = loadGraph()
    expect(isLoading.value).toBe(true)

    resolveGraph(MOCK_GRAPH)
    await promise
    expect(isLoading.value).toBe(false)
  })
})
