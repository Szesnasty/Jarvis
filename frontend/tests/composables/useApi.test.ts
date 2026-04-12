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
})
