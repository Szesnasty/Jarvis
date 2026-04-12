import type { HealthResponse, WorkspaceStatusResponse, WorkspaceInitResponse, NoteMetadata, NoteDetail, ReindexResponse } from '~/types'

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

  return { fetchHealth, fetchWorkspaceStatus, initWorkspace, fetchNotes, fetchNote, deleteNote }
}
