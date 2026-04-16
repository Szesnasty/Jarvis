import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useChat } from '~/composables/useChat'

// Mock useWebSocket at module level
const mockConnect = vi.fn()
const mockSend = vi.fn().mockReturnValue(true)
const mockClose = vi.fn()
let messageHandler: ((event: any) => void) | null = null

vi.mock('~/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: ref(true),
    connect: mockConnect,
    send: mockSend,
    close: mockClose,
    setSessionId: vi.fn(),
    onReconnect: () => () => {},
    onMessage: (handler: (event: any) => void) => {
      messageHandler = handler
      return () => { messageHandler = null }
    },
  }),
}))

// Mock useApiKeys to set provider
let mockProvider = ref('anthropic')

vi.mock('~/composables/useApiKeys', () => ({
  useApiKeys: () => ({
    activeProvider: mockProvider,
    activeKey: ref('sk-test'),
    activeModel: ref('claude-sonnet-4-20250514'),
    isConfigured: () => true,
    selectModel: vi.fn(),
  }),
  MODEL_CATALOG: {},
}))

vi.mock('~/composables/useLocalModels', () => ({
  useLocalModels: () => ({
    baseUrl: ref('http://localhost:11434'),
    ollamaDown: ref(false),
    activeModel: computed(() => null),
    runtime: ref(null),
    startHealthPolling: vi.fn(),
    stopHealthPolling: vi.fn(),
    warmUpModel: vi.fn(),
    fetchRuntime: vi.fn(),
  }),
}))

function simulateEvent(event: any) {
  if (messageHandler) messageHandler(event)
}

describe('local model chat integration', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockProvider.value = 'ollama'
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('sends provider=ollama without api_key', () => {
    const { init, sendMessage } = useChat()
    init()
    sendMessage('Hello')
    expect(mockSend).toHaveBeenCalledWith(
      expect.objectContaining({
        provider: 'ollama',
        base_url: 'http://localhost:11434',
      }),
    )
    // Should NOT have api_key
    const payload = mockSend.mock.calls[mockSend.mock.calls.length - 1][0]
    expect(payload.api_key).toBeUndefined()
  })

  it('shows slow response indicator after 10s', () => {
    const { init, sendMessage, slowResponse } = useChat()
    init()
    sendMessage('Hello')

    expect(slowResponse.value).toBe('')
    vi.advanceTimersByTime(10_001)
    expect(slowResponse.value).toContain('loading')
  })

  it('shows extended slow message after 30s', () => {
    const { init, sendMessage, slowResponse } = useChat()
    init()
    sendMessage('Hello')

    vi.advanceTimersByTime(30_001)
    expect(slowResponse.value).toContain('Still generating')
  })

  it('clears slow indicator when text arrives', () => {
    const { init, sendMessage, slowResponse } = useChat()
    init()
    sendMessage('Hello')

    vi.advanceTimersByTime(10_001)
    expect(slowResponse.value).not.toBe('')

    simulateEvent({ type: 'text_delta', content: 'Hi' })
    expect(slowResponse.value).toBe('')
  })

  it('does not start slow timer for cloud providers', () => {
    mockProvider.value = 'anthropic'
    const { init, sendMessage, slowResponse } = useChat()
    init()
    sendMessage('Hello')

    vi.advanceTimersByTime(15_000)
    expect(slowResponse.value).toBe('')
  })

  it('clears slow indicator on done event', () => {
    const { init, sendMessage, slowResponse } = useChat()
    init()
    sendMessage('Hello')

    vi.advanceTimersByTime(10_001)
    expect(slowResponse.value).not.toBe('')

    simulateEvent({ type: 'done', session_id: 'abc' })
    expect(slowResponse.value).toBe('')
  })
})
