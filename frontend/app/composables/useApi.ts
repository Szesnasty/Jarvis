import type { HealthResponse, WorkspaceStatusResponse, WorkspaceInitResponse, NoteMetadata, NoteDetail, ReindexResponse, SessionMetadata, SessionDetail } from '~/types'

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

  return { fetchHealth, fetchWorkspaceStatus, initWorkspace, fetchNotes, fetchNote, deleteNote, fetchSessions, fetchSession, resumeSession, fetchPreferences, setPreference }
}
