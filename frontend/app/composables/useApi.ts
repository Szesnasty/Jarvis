import type { HealthResponse, WorkspaceStatusResponse, WorkspaceInitResponse, NoteMetadata, NoteDetail, ReindexResponse, SessionMetadata, SessionDetail, GraphData, GraphStats, GraphNode, SpecialistSummary, SpecialistDetail } from '~/types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function useApi() {
  async function fetchHealth(): Promise<HealthResponse> {
    try {
      return await $fetch<HealthResponse>('/api/health')
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchWorkspaceStatus(): Promise<WorkspaceStatusResponse> {
    try {
      return await $fetch<WorkspaceStatusResponse>('/api/workspace/status')
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function initWorkspace(apiKey: string): Promise<WorkspaceInitResponse> {
    try {
      return await $fetch<WorkspaceInitResponse>('/api/workspace/init', {
        method: 'POST',
        body: { api_key: apiKey },
      })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchNotes(params?: { folder?: string; search?: string; limit?: number }): Promise<NoteMetadata[]> {
    try {
      return await $fetch<NoteMetadata[]>('/api/memory/notes', { params })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchNote(path: string): Promise<NoteDetail> {
    try {
      return await $fetch<NoteDetail>(`/api/memory/notes/${path}`)
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function deleteNote(path: string): Promise<void> {
    try {
      await $fetch(`/api/memory/notes/${path}`, { method: 'DELETE' })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchSessions(limit = 20): Promise<SessionMetadata[]> {
    try {
      return await $fetch<SessionMetadata[]>('/api/sessions', { params: { limit } })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchSession(sessionId: string): Promise<SessionDetail> {
    try {
      return await $fetch<SessionDetail>(`/api/sessions/${sessionId}`)
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function resumeSession(sessionId: string): Promise<{ session_id: string; status: string }> {
    try {
      return await $fetch<{ session_id: string; status: string }>(`/api/sessions/${sessionId}/resume`, { method: 'POST' })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchPreferences(): Promise<Record<string, string>> {
    try {
      return await $fetch<Record<string, string>>('/api/preferences')
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function setPreference(key: string, value: string): Promise<Record<string, string>> {
    try {
      return await $fetch<Record<string, string>>('/api/preferences', { method: 'PATCH', body: { key, value } })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchGraph(): Promise<GraphData> {
    try {
      return await $fetch<GraphData>('/api/graph')
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchGraphStats(): Promise<GraphStats> {
    try {
      return await $fetch<GraphStats>('/api/graph/stats')
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchGraphNeighbors(nodeId: string, depth = 1): Promise<GraphNode[]> {
    try {
      return await $fetch<GraphNode[]>('/api/graph/neighbors', { params: { node_id: nodeId, depth } })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function rebuildGraph(): Promise<GraphStats> {
    try {
      return await $fetch<GraphStats>('/api/graph/rebuild', { method: 'POST' })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchSpecialists(): Promise<SpecialistSummary[]> {
    try {
      return await $fetch<SpecialistSummary[]>('/api/specialists')
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchSpecialist(id: string): Promise<SpecialistDetail> {
    try {
      return await $fetch<SpecialistDetail>(`/api/specialists/${id}`)
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function createSpecialist(data: Partial<SpecialistDetail>): Promise<SpecialistDetail> {
    try {
      return await $fetch<SpecialistDetail>('/api/specialists', { method: 'POST', body: data })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function updateSpecialist(id: string, data: Partial<SpecialistDetail>): Promise<SpecialistDetail> {
    try {
      return await $fetch<SpecialistDetail>(`/api/specialists/${id}`, { method: 'PUT', body: data })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function deleteSpecialist(id: string): Promise<void> {
    try {
      await $fetch(`/api/specialists/${id}`, { method: 'DELETE' })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function activateSpecialist(id: string): Promise<{ status: string }> {
    try {
      return await $fetch<{ status: string }>(`/api/specialists/activate/${id}`, { method: 'POST' })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function deactivateSpecialist(): Promise<{ status: string }> {
    try {
      return await $fetch<{ status: string }>('/api/specialists/deactivate', { method: 'POST' })
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  async function fetchActiveSpecialist(): Promise<SpecialistDetail | null> {
    try {
      const result = await $fetch<SpecialistDetail | { active: null }>('/api/specialists/active')
      if ('active' in result && result.active === null) return null
      return result as SpecialistDetail
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'status' in error) {
        const status = (error as { status: number }).status
        const message = (error as { statusMessage?: string }).statusMessage ?? 'Request failed'
        throw new ApiError(status, message)
      }
      throw new ApiError(0, 'Network error')
    }
  }

  return { fetchHealth, fetchWorkspaceStatus, initWorkspace, fetchNotes, fetchNote, deleteNote, fetchSessions, fetchSession, resumeSession, fetchPreferences, setPreference, fetchGraph, fetchGraphStats, fetchGraphNeighbors, rebuildGraph, fetchSpecialists, fetchSpecialist, createSpecialist, updateSpecialist, deleteSpecialist, activateSpecialist, deactivateSpecialist, fetchActiveSpecialist }
}
