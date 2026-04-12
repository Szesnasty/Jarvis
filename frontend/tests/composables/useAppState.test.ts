import { describe, it, expect, vi } from 'vitest'
import { registerEndpoint } from '@nuxt/test-utils/runtime'

describe('useAppState', () => {
  it('initial isInitialized is false', () => {
    const { isInitialized } = useAppState()
    expect(isInitialized.value).toBe(false)
  })

  it('initial backendStatus is unknown', () => {
    const { backendStatus } = useAppState()
    expect(backendStatus.value).toBe('unknown')
  })

  it('checkHealth() sets backendStatus to online when API returns 200', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))

    const { backendStatus, checkHealth } = useAppState()
    await checkHealth()
    expect(backendStatus.value).toBe('online')
  })

  it('checkHealth() sets backendStatus to offline when API throws', async () => {
    registerEndpoint('/api/health', {
      handler: () => {
        throw createError({ statusCode: 500, statusMessage: 'fail' })
      },
    })

    const { backendStatus, checkHealth } = useAppState()
    await checkHealth()
    expect(backendStatus.value).toBe('offline')
  })

  it('checkHealth() does not change isInitialized', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))

    const { isInitialized, checkHealth } = useAppState()
    const before = isInitialized.value
    await checkHealth()
    expect(isInitialized.value).toBe(before)
  })

  it('state persists across multiple calls to useAppState()', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))

    const state1 = useAppState()
    await state1.checkHealth()
    const state2 = useAppState()
    expect(state2.backendStatus.value).toBe('online')
  })

  it('latest result wins when checkHealth() called twice', async () => {
    // First call succeeds
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))

    const state = useAppState()
    await state.checkHealth()
    expect(state.backendStatus.value).toBe('online')

    // Second call fails
    registerEndpoint('/api/health', {
      handler: () => {
        throw createError({ statusCode: 500, statusMessage: 'fail' })
      },
    })

    await state.checkHealth()
    expect(state.backendStatus.value).toBe('offline')
  })
})
