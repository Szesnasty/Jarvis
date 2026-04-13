import type { ChatMessage, WsEvent } from '~/types'
import { useWebSocket } from '~/composables/useWebSocket'

export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const currentResponse = ref('')
  const isLoading = ref(false)
  const toolActivity = ref('')
  const error = ref('')
  const sessionId = ref('')
  const canRetry = ref(false)
  let _lastContent = ''
  let _errorClearTimer: ReturnType<typeof setTimeout> | null = null

  const { isConnected, connect, send, onMessage, close, onReconnect } = useWebSocket()

  function _setError(msg: string, retryable = false): void {
    error.value = msg
    canRetry.value = retryable
    if (_errorClearTimer) clearTimeout(_errorClearTimer)
    _errorClearTimer = setTimeout(() => { error.value = ''; canRetry.value = false }, 8000)
  }

  function _handleEvent(event: WsEvent): void {
    if (event.type === 'session_start') {
      sessionId.value = event.session_id
      return
    }

    if (event.type === 'text_delta') {
      currentResponse.value += event.content
      return
    }

    if (event.type === 'tool_use') {
      const label = _toolLabel(event.name)
      toolActivity.value = label
      return
    }

    if (event.type === 'tool_result') {
      toolActivity.value = ''
      return
    }

    if (event.type === 'done') {
      if (currentResponse.value) {
        messages.value.push({ role: 'assistant', content: currentResponse.value })
        currentResponse.value = ''
      }
      isLoading.value = false
      toolActivity.value = ''
      return
    }

    if (event.type === 'error') {
      const content = event.content || 'Something went wrong.'
      const retryable = /try again|overloaded|rate limit|reconnect/i.test(content)
      _setError(content, retryable)
      isLoading.value = false
      toolActivity.value = ''
      return
    }

    // WebSocket disconnected mid-response — reset loading state
    if ((event as any).type === 'disconnected') {
      if (isLoading.value) {
        if (currentResponse.value) {
          messages.value.push({ role: 'assistant', content: currentResponse.value + ' *(connection lost)*' })
          currentResponse.value = ''
        }
        isLoading.value = false
        toolActivity.value = ''
        _setError('Connection lost — reconnecting...', true)
      }
    }
  }

  function _toolLabel(name: string): string {
    const labels: Record<string, string> = {
      search_notes: 'Searching notes...',
      read_note: 'Reading note...',
      write_note: 'Writing note...',
      append_note: 'Updating note...',
    }
    return labels[name] ?? `Running ${name}...`
  }

  function init(): void {
    connect()
    onMessage(_handleEvent)
    // When WS reconnects, session_start fires automatically from backend
    onReconnect(() => {
      sessionId.value = ''
      error.value = ''
      canRetry.value = false
    })
  }

  function sendMessage(content: string): void {
    if (!content.trim() || isLoading.value) return

    _lastContent = content.trim()
    messages.value.push({ role: 'user', content: _lastContent })
    currentResponse.value = ''
    error.value = ''
    canRetry.value = false
    isLoading.value = true

    const sent = send({ type: 'message', content: _lastContent, session_id: sessionId.value })
    if (!sent) {
      // WS not ready — reset and show error
      isLoading.value = false
      _setError('Not connected — reconnecting, try again in a moment.', true)
    }
  }

  function retry(): void {
    if (!_lastContent || isLoading.value) return
    // Remove the last user message to re-send cleanly
    const last = messages.value[messages.value.length - 1]
    if (last?.role === 'user' && last.content === _lastContent) {
      messages.value.pop()
    }
    error.value = ''
    canRetry.value = false
    sendMessage(_lastContent)
  }

  function disconnect(): void {
    close()
  }

  return {
    messages,
    currentResponse,
    isLoading,
    toolActivity,
    error,
    canRetry,
    sessionId,
    isConnected,
    init,
    sendMessage,
    retry,
    disconnect,
  }
}
