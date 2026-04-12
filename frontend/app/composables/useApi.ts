import type { HealthResponse } from '~/types'

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

  return { fetchHealth }
}
