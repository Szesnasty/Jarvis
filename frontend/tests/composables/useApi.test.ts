import { describe, it, expect, vi } from 'vitest'
import { registerEndpoint } from '@nuxt/test-utils/runtime'
import { ApiError, useApi } from '~/composables/useApi'

describe('useApi', () => {
  describe('fetchHealth()', () => {
    it('returns health response on 200', async () => {
      registerEndpoint('/api/health', () => ({
        status: 'ok',
        version: '0.1.0',
      }))

      const { fetchHealth } = useApi()
      const result = await fetchHealth()
      expect(result).toEqual({ status: 'ok', version: '0.1.0' })
    })

    it('throws ApiError with status code on 500', async () => {
      registerEndpoint('/api/health', {
        handler: () => {
          throw createError({ statusCode: 500, statusMessage: 'Internal Server Error' })
        },
      })

      const { fetchHealth } = useApi()
      await expect(fetchHealth()).rejects.toThrow()
    })

    it('throws ApiError with message on 404', async () => {
      registerEndpoint('/api/health', {
        handler: () => {
          throw createError({ statusCode: 404, statusMessage: 'Not Found' })
        },
      })

      const { fetchHealth } = useApi()
      await expect(fetchHealth()).rejects.toThrow()
    })
  })

  describe('ApiError', () => {
    it('has correct status and message properties', () => {
      const error = new ApiError(500, 'Server error')
      expect(error.status).toBe(500)
      expect(error.message).toBe('Server error')
    })

    it('is instanceof Error', () => {
      const error = new ApiError(404, 'Not found')
      expect(error).toBeInstanceOf(Error)
    })

    it('has name ApiError', () => {
      const error = new ApiError(0, 'test')
      expect(error.name).toBe('ApiError')
    })
  })

  describe('fetchWorkspaceStatus()', () => {
    it('returns workspace status on 200', async () => {
      registerEndpoint('/api/workspace/status', () => ({
        initialized: true,
        workspace_path: '/tmp/Jarvis',
        api_key_set: true,
      }))

      const { fetchWorkspaceStatus } = useApi()
      const result = await fetchWorkspaceStatus()
      expect(result.initialized).toBe(true)
    })

    it('returns not initialized when workspace absent', async () => {
      registerEndpoint('/api/workspace/status', () => ({
        initialized: false,
      }))

      const { fetchWorkspaceStatus } = useApi()
      const result = await fetchWorkspaceStatus()
      expect(result.initialized).toBe(false)
    })
  })

  describe('initWorkspace()', () => {
    it('sends POST and returns response', async () => {
      registerEndpoint('/api/workspace/init', {
        method: 'POST',
        handler: () => ({
          status: 'ok',
          workspace_path: '/tmp/Jarvis',
        }),
      })

      const { initWorkspace } = useApi()
      const result = await initWorkspace('sk-ant-test-key')
      expect(result.status).toBe('ok')
      expect(result.workspace_path).toBe('/tmp/Jarvis')
    })

    it('throws on 409 conflict', async () => {
      registerEndpoint('/api/workspace/init', {
        method: 'POST',
        handler: () => {
          throw createError({ statusCode: 409, statusMessage: 'Workspace already exists' })
        },
      })

      const { initWorkspace } = useApi()
      await expect(initWorkspace('sk-ant-test-key')).rejects.toThrow()
    })
  })
})
