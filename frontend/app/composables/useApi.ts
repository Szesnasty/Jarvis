import type { HealthResponse, WorkspaceStatusResponse, WorkspaceInitResponse, NoteMetadata, NoteDetail, ReindexResponse, SessionMetadata, SessionDetail, GraphData, GraphStats, GraphNode, GraphNodeDetail, GraphOrphan, SpecialistSummary, SpecialistDetail, SpecialistFileInfo, UrlIngestResult, JarvisSelfConfig, SemanticOrphan, ConnectionResult } from '~/types'
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

  // --- Connections (Smart Connect) ---

  const fetchSemanticOrphans = () =>
    _api<SemanticOrphan[]>('/api/connections/orphans')

  const rerunConnect = (notePath: string, mode: 'fast' | 'aggressive' = 'fast') =>
    _api<ConnectionResult>(
      `/api/connections/run/${notePath.split('/').map(encodeURIComponent).join('/')}?mode=${mode}`,
      { method: 'POST' },
    )

  const dismissSuggestion = (notePath: string, targetPath: string) =>
    _api<{ note_path: string; target_path: string; dismissed: boolean }>(
      '/api/connections/dismiss',
      { method: 'POST', body: { note_path: notePath, target_path: targetPath } },
    )

  const promoteSuggestion = (notePath: string, targetPath: string) =>
    _api<{ note_path: string; target_path: string; related: string[] }>(
      '/api/connections/promote',
      { method: 'POST', body: { note_path: notePath, target_path: targetPath } },
    )

  const promoteBulk = (minConfidence = 0.8, scope: string = 'all', dryRun = false) =>
    _api<{
      promoted: number
      notes_changed: number
      skipped: number
      scanned: number
      min_confidence: number
      dry_run: boolean
    }>('/api/connections/promote-bulk', {
      method: 'POST',
      body: { min_confidence: minConfidence, scope, dry_run: dryRun },
    })

  const fetchConnectionsCoverage = () =>
    _api<{
      notes_total: number
      notes_with_suggestions: number
      notes_pending: number
      sections_total: number
      sections_with_suggestions: number
      sections_pending: number
      sections_unprocessed: number     // SC never ran → needs backfill
      sections_no_match: number        // SC ran, found nothing → final state
      documents_pending: number
      pending_strong_suggestions: number
      pending_strong_notes: number
      strong_threshold: number
      active_section_jobs: Array<{ id: string; name: string; kind: string; stage?: string }>
      pending_note_paths: string[]     // relative paths in memory/ with suggested_related awaiting review
    }>('/api/connections/coverage')

  return { fetchHealth, fetchWorkspaceStatus, initWorkspace, fetchNotes, semanticSearchNotes, fetchNote, deleteNote, fetchSessions, fetchSession, resumeSession, deleteSession, fetchPreferences, setPreference, fetchGraph, fetchGraphStats, fetchGraphNeighbors, rebuildGraph, fetchNodeDetail, fetchOrphans, createEdge, fetchSpecialists, fetchSpecialist, createSpecialist, updateSpecialist, deleteSpecialist, activateSpecialist, deactivateSpecialist, fetchActiveSpecialist, ingestUrl, fetchSpecialistFiles, uploadSpecialistFile, ingestSpecialistUrl, deleteSpecialistFile, fetchJarvisConfig, updateJarvisConfig, fetchSemanticOrphans, rerunConnect, dismissSuggestion, promoteSuggestion, promoteBulk, fetchConnectionsCoverage }
}
