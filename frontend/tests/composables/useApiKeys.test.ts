import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock useState for SSR compatibility in tests
const stateStore = new Map<string, { value: unknown }>()
vi.stubGlobal('useState', (key: string, init?: () => unknown) => {
  if (!stateStore.has(key)) {
    stateStore.set(key, { value: init?.() })
  }
  return stateStore.get(key)!
})
vi.stubGlobal('computed', (fn: () => unknown) => ({ value: fn() }))

// Must import after mocking globals
import { useApiKeys } from '~/composables/useApiKeys'

// Mock Storage
function createMockStorage(): Storage {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => { store.set(key, value) },
    removeItem: (key: string) => { store.delete(key) },
    clear: () => store.clear(),
    get length() { return store.size },
    key: (_index: number) => null,
  }
}

describe('useApiKeys', () => {
  let mockSession: Storage
  let mockLocal: Storage

  beforeEach(() => {
    stateStore.clear()
    mockSession = createMockStorage()
    mockLocal = createMockStorage()
    vi.stubGlobal('sessionStorage', mockSession)
    vi.stubGlobal('localStorage', mockLocal)
  })

  it('has 3 providers', () => {
    const { providers } = useApiKeys()
    expect(providers).toHaveLength(3)
    expect(providers.map(p => p.id)).toEqual(['anthropic', 'openai', 'google'])
  })

  it('returns null for unconfigured provider', () => {
    const { getKey } = useApiKeys()
    expect(getKey('anthropic')).toBeNull()
  })

  it('stores key in sessionStorage by default', () => {
    const { setKey, getKey, isConfigured } = useApiKeys()
    setKey('anthropic', 'sk-ant-test123', false)
    expect(getKey('anthropic')).toBe('sk-ant-test123')
    expect(isConfigured('anthropic')).toBe(true)
    expect(mockSession.getItem('jarvis_key_anthropic')).toBe('sk-ant-test123')
    expect(mockLocal.getItem('jarvis_key_anthropic')).toBeNull()
  })

  it('stores key in localStorage when remember=true', () => {
    const { setKey, getKey } = useApiKeys()
    setKey('openai', 'sk-test-openai', true)
    expect(getKey('openai')).toBe('sk-test-openai')
    expect(mockLocal.getItem('jarvis_key_openai')).toBe('sk-test-openai')
    expect(mockSession.getItem('jarvis_key_openai')).toBeNull()
  })

  it('removes key from both storages', () => {
    const { setKey, removeKey, getKey, isConfigured } = useApiKeys()
    setKey('anthropic', 'sk-ant-test', true)
    expect(isConfigured('anthropic')).toBe(true)
    removeKey('anthropic')
    expect(getKey('anthropic')).toBeNull()
    expect(isConfigured('anthropic')).toBe(false)
    expect(mockLocal.getItem('jarvis_key_anthropic')).toBeNull()
    expect(mockSession.getItem('jarvis_key_anthropic')).toBeNull()
  })

  it('masks key with provider prefix', () => {
    const { setKey, getMaskedKey } = useApiKeys()
    setKey('anthropic', 'sk-ant-very-long-key-123', false)
    expect(getMaskedKey('anthropic')).toBe('sk-ant-****')
  })

  it('returns empty string for masked key when not configured', () => {
    const { getMaskedKey } = useApiKeys()
    expect(getMaskedKey('anthropic')).toBe('')
  })

  it('tracks remember status', () => {
    const { setKey, isRemembered } = useApiKeys()
    setKey('anthropic', 'sk-ant-test', false)
    expect(isRemembered('anthropic')).toBe(false)
    setKey('anthropic', 'sk-ant-test', true)
    expect(isRemembered('anthropic')).toBe(true)
  })

  it('hasAnyKey returns false when no keys configured', () => {
    const { hasAnyKey } = useApiKeys()
    expect(hasAnyKey()).toBe(false)
  })

  it('hasAnyKey returns true when at least one key configured', () => {
    const { setKey, hasAnyKey } = useApiKeys()
    setKey('google', 'AIza-test', false)
    expect(hasAnyKey()).toBe(true)
  })

  it('prefers localStorage over sessionStorage on read', () => {
    const { getKey } = useApiKeys()
    mockLocal.setItem('jarvis_key_anthropic', 'remembered-key')
    mockSession.setItem('jarvis_key_anthropic', 'session-key')
    expect(getKey('anthropic')).toBe('remembered-key')
  })
})
