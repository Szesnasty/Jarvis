import { describe, it, expect, vi } from 'vitest'
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

function simulateEvent(event: any) {
  if (messageHandler) messageHandler(event)
}

describe('useChat', () => {
  it('sendMessage connects WebSocket via init', () => {
    const { init } = useChat()
    init()
    expect(mockConnect).toHaveBeenCalled()
  })

  it('sendMessage sends JSON with content field', () => {
    const { init, sendMessage } = useChat()
    init()
    sendMessage('Hello')
    expect(mockSend).toHaveBeenCalledWith(
      expect.objectContaining({ content: 'Hello' }),
    )
  })

  it('streaming chunks update currentResponse progressively', () => {
    const { init, sendMessage, currentResponse } = useChat()
    init()
    sendMessage('Hi')

    simulateEvent({ type: 'text_delta', content: 'Hello ' })
    expect(currentResponse.value).toBe('Hello ')

    simulateEvent({ type: 'text_delta', content: 'world' })
    expect(currentResponse.value).toBe('Hello world')
  })

  it('currentResponse cleared when new message sent', () => {
    const { init, sendMessage, currentResponse } = useChat()
    init()
    sendMessage('First')

    simulateEvent({ type: 'text_delta', content: 'Response' })
    simulateEvent({ type: 'done', session_id: 'abc' })

    // currentResponse should be cleared after done
    expect(currentResponse.value).toBe('')

    sendMessage('Second')
    // Should be empty for new message
    expect(currentResponse.value).toBe('')
  })

  it('isLoading is true during streaming, false after', () => {
    const { init, sendMessage, isLoading } = useChat()
    init()

    expect(isLoading.value).toBe(false)
    sendMessage('Hi')
    expect(isLoading.value).toBe(true)

    simulateEvent({ type: 'text_delta', content: 'Reply' })
    expect(isLoading.value).toBe(true)

    simulateEvent({ type: 'done', session_id: 'abc' })
    expect(isLoading.value).toBe(false)
  })

  it('tool use event updates toolActivity', () => {
    const { init, sendMessage, toolActivity } = useChat()
    init()
    sendMessage('Search')

    simulateEvent({ type: 'tool_use', name: 'search_notes', input: { query: 'test' } })
    expect(toolActivity.value).toBe('Searching notes...')
  })

  it('tool result clears toolActivity', () => {
    const { init, sendMessage, toolActivity } = useChat()
    init()
    sendMessage('Search')

    simulateEvent({ type: 'tool_use', name: 'search_notes', input: {} })
    expect(toolActivity.value).toBeTruthy()

    simulateEvent({ type: 'tool_result', name: 'search_notes', content: '[]' })
    expect(toolActivity.value).toBe('')
  })

  it('trace event before done attaches trace to the assistant message', () => {
    const { init, sendMessage, messages } = useChat()
    init()
    sendMessage('hi')

    simulateEvent({ type: 'text_delta', content: 'ok' })
    simulateEvent({ type: 'trace', items: [
      { path: 'inbox/a.md', title: 'A', score: 0.81, reason: 'primary', via: 'cosine', signals: { cosine: 0.81 } },
    ] })
    simulateEvent({ type: 'done', session_id: 'abc' })

    const assistantMsg = messages.value.find(m => m.role === 'assistant')
    expect(assistantMsg?.trace).toHaveLength(1)
    expect(assistantMsg?.trace?.[0]?.path).toBe('inbox/a.md')
  })

  it('trace from one message does not leak into the next', () => {
    const { init, sendMessage, messages } = useChat()
    init()

    sendMessage('first')
    simulateEvent({ type: 'text_delta', content: 'reply 1' })
    simulateEvent({ type: 'trace', items: [
      { path: 'inbox/a.md', title: 'A', score: 0.5, reason: 'primary', via: 'bm25' },
    ] })
    simulateEvent({ type: 'done', session_id: 'abc' })

    sendMessage('second')
    simulateEvent({ type: 'text_delta', content: 'reply 2' })
    // No trace event this time.
    simulateEvent({ type: 'done', session_id: 'abc' })

    const assistantMsgs = messages.value.filter(m => m.role === 'assistant')
    expect(assistantMsgs).toHaveLength(2)
    expect(assistantMsgs[0]?.trace).toHaveLength(1)
    expect(assistantMsgs[1]?.trace).toBeUndefined()
  })

  it('session messages array grows after each exchange', () => {
    const { init, sendMessage, messages } = useChat()
    init()

    sendMessage('Hi')
    expect(messages.value).toHaveLength(1)
    expect(messages.value[0]!.role).toBe('user')

    simulateEvent({ type: 'text_delta', content: 'Hello' })
    simulateEvent({ type: 'done', session_id: 'abc' })

    expect(messages.value).toHaveLength(2)
    expect(messages.value[1]!.role).toBe('assistant')
  })

  it('error event sets error ref', () => {
    const { init, sendMessage, error } = useChat()
    init()
    sendMessage('Hi')

    simulateEvent({ type: 'error', content: 'Something went wrong' })
    expect(error.value).toBe('Something went wrong')
  })

  it('error sets isLoading to false', () => {
    const { init, sendMessage, isLoading } = useChat()
    init()
    sendMessage('Hi')
    expect(isLoading.value).toBe(true)

    simulateEvent({ type: 'error', content: 'fail' })
    expect(isLoading.value).toBe(false)
  })
})
