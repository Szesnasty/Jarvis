import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetchPreferences = vi.fn()
const mockSetPreference = vi.fn()

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    fetchPreferences: mockFetchPreferences,
    setPreference: mockSetPreference,
  }),
}))

import { usePreferences } from '~/composables/usePreferences'

describe('usePreferences', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loadPreferences fetches from API', async () => {
    mockFetchPreferences.mockResolvedValue({ style: 'concise' })
    const { preferences, loadPreferences } = usePreferences()

    await loadPreferences()
    expect(mockFetchPreferences).toHaveBeenCalledOnce()
    expect(preferences.value).toEqual({ style: 'concise' })
  })

  it('setPreference sends PATCH via API', async () => {
    mockSetPreference.mockResolvedValue({ style: 'verbose' })
    const { setPreference } = usePreferences()

    await setPreference('style', 'verbose')
    expect(mockSetPreference).toHaveBeenCalledWith('style', 'verbose')
  })

  it('preferences available as reactive state', async () => {
    mockFetchPreferences.mockResolvedValue({ a: '1', b: '2' })
    const { preferences, loadPreferences } = usePreferences()

    expect(preferences.value).toEqual({})
    await loadPreferences()
    expect(preferences.value).toEqual({ a: '1', b: '2' })
  })

  it('optimistic update: UI updates before API confirms', async () => {
    let resolveApi!: (v: Record<string, string>) => void
    mockSetPreference.mockReturnValue(new Promise((r) => { resolveApi = r }))

    const { preferences, setPreference } = usePreferences()

    const promise = setPreference('style', 'brief')
    // Optimistic: value is already set
    expect(preferences.value.style).toBe('brief')

    resolveApi({ style: 'brief' })
    await promise
    expect(preferences.value.style).toBe('brief')
  })
})
