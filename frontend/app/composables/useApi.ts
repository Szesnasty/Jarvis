import type { HealthResponse, WorkspaceStatusResponse, WorkspaceInitResponse, NoteMetadata, NoteDetail, ReindexResponse, SessionMetadata, SessionDetail, GraphData, GraphStats, GraphNode, GraphNodeDetail, GraphOrphan, SpecialistSummary, SpecialistDetail, SpecialistFileInfo, UrlIngestResult, JarvisSelfConfig } from '~/types'
import { ApiError } from '~/types'

function _wrapError(error: unknown): never {
  if (error && typeof error === 'object' && 'status' in error) {
    const status = (error as { status: number }).status
    const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
    throw new ApiError(status, message)
  }
  throw new ApiError(0, 'Network error')
}

async function _api<T>(url: string, opts?: Parameters<typeof $fetch>[1]): Promise<T> {
  try {
    return await $fetch<T>(url, opts)
  } catch (error: unknown) {
    _wrapError(error)
  }
}

export function useApi() {
  const fetchHealth = () => _api<HealthResponse>('/api/health')
  const fetchWorkspaceStatus = () => _api<WorkspaceStatusResponse>('/api/workspace/status')

  const initWorkspace = (apiKey?: string) =>
    _api<WorkspaceInitResponse>('/api/workspace/init', {
      method: 'POST',
      body: apiKey ? { api_key: apiKey } : {},
    })

  const fetchNotes = (params?: { folder?: string; search?: string; limit?: number }) =>
    _api<NoteMetadata[]>('/api/memory/notes', { params })

  const semanticSearchNotes = (q: string, limit = 10) =>
    _api<{ results: { path: string; similarity: number }[]; mode: string; error?: string }>(
      '/api/memory/semantic-search',
      { params: { q, limit } },
    )

  const fetchNote = (path: string) =>
    _api<NoteDetail>(`/api/memory/notes/${encodeURIComponent(path)}`)

  const deleteNote = (path: string) =>
    _api<void>(`/api/memory/notes/${encodeURIComponent(path)}`, { method: 'DELETE' })

  const fetchSessions = (limit = 20) =>
    _api<SessionMetadata[]>('/api/sessions', { params: { limit } })

  const fetchSession = (sessionId: string) =>
    _api<SessionDetail>(`/api/sessions/${sessionId}`)

  const resumeSession = (sessionId: string) =>
    _api<{ session_id: string; status: string }>(`/api/sessions/${sessionId}/resume`, { method: 'POST' })

  const deleteSession = (sessionId: string) =>
    _api<void>(`/api/sessions/${sessionId}`, { method: 'DELETE' })

  const fetchPreferences = () =>
    _api<Record<string, string>>('/api/preferences')

  const setPreference = (key: string, value: string) =>
    _api<Record<string, string>>('/api/preferences', { method: 'PATCH', body: { key, value } })

  const fetchGraph = () => _api<GraphData>('/api/graph')
  const fetchGraphStats = () => _api<GraphStats>('/api/graph/stats')

  const fetchGraphNeighbors = (nodeId: string, depth = 1) =>
    _api<GraphNode[]>('/api/graph/neighbors', { params: { node_id: nodeId, depth } })

  const rebuildGraph = () =>
    _api<GraphStats>('/api/graph/rebuild', { method: 'POST' })

  const fetchNodeDetail = (nodeId: string) =>
    _api<GraphNodeDetail>(`/api/graph/nodes/${encodeURIComponent(nodeId)}/detail`)

  const fetchOrphans = () =>
    _api<GraphOrphan[]>('/api/graph/orphans')

  const createEdge = (source: string, target: string, type = 'related') =>
    _api<{ status: string; edge: { source: string; target: string; type: string } }>('/api/graph/edges', { method: 'POST', body: { source, target, type } })

  const fetchSpecialists = () => _api<SpecialistSummary[]>('/api/specialists')

  const fetchSpecialist = (id: string) =>
    _api<SpecialistDetail>(`/api/specialists/${id}`)

  const createSpecialist = (data: Partial<SpecialistDetail>) =>
    _api<SpecialistDetail>('/api/specialists', { method: 'POST', body: data })

  const updateSpecialist = (id: string, data: Partial<SpecialistDetail>) =>
    _api<SpecialistDetail>(`/api/specialists/${id}`, { method: 'PUT', body: data })

  const deleteSpecialist = (id: string) =>
    _api<void>(`/api/specialists/${id}`, { method: 'DELETE' })

  const activateSpecialist = (id: string) =>
    _api<{ status: string }>(`/api/specialists/activate/${id}`, { method: 'POST' })

  const deactivateSpecialist = (id?: string) =>
    _api<{ status: string }>(id ? `/api/specialists/deactivate/${id}` : '/api/specialists/deactivate', { method: 'POST' })

  async function fetchActiveSpecialist(): Promise<SpecialistDetail[]> {
    const result = await _api<SpecialistDetail[]>('/api/specialists/active')
    return Array.isArray(result) ? result : []
  }

  const ingestUrl = (url: string, folder = 'knowledge', summarize = false) =>
    _api<UrlIngestResult>('/api/memory/ingest-url', { method: 'POST', body: { url, folder, summarize } })

  // --- Specialist Files ---

  const fetchSpecialistFiles = (id: string) =>
    _api<SpecialistFileInfo[]>(`/api/specialists/${id}/files`)

  const uploadSpecialistFile = async (id: string, file: File): Promise<SpecialistFileInfo> => {
    const formData = new FormData()
    formData.append('file', file)
    return _api<SpecialistFileInfo>(`/api/specialists/${id}/files`, { method: 'POST', body: formData })
  }

  const ingestSpecialistUrl = (id: string, url: string, summarize = false) =>
    _api<SpecialistFileInfo>(`/api/specialists/${id}/ingest-url`, { method: 'POST', body: { url, summarize } })

  const deleteSpecialistFile = (id: string, filename: string) =>
    _api<void>(`/api/specialists/${id}/files/${encodeURIComponent(filename)}`, { method: 'DELETE' })

  // --- JARVIS self-config ---

  const fetchJarvisConfig = () =>
    _api<JarvisSelfConfig>('/api/specialists/jarvis/config')

  const updateJarvisConfig = (data: Partial<JarvisSelfConfig>) =>
    _api<JarvisSelfConfig>('/api/specialists/jarvis/config', { method: 'PUT', body: data })

  return { fetchHealth, fetchWorkspaceStatus, initWorkspace, fetchNotes, semanticSearchNotes, fetchNote, deleteNote, fetchSessions, fetchSession, resumeSession, deleteSession, fetchPreferences, setPreference, fetchGraph, fetchGraphStats, fetchGraphNeighbors, rebuildGraph, fetchNodeDetail, fetchOrphans, createEdge, fetchSpecialists, fetchSpecialist, createSpecialist, updateSpecialist, deleteSpecialist, activateSpecialist, deactivateSpecialist, fetchActiveSpecialist, ingestUrl, fetchSpecialistFiles, uploadSpecialistFile, ingestSpecialistUrl, deleteSpecialistFile, fetchJarvisConfig, updateJarvisConfig }
}
