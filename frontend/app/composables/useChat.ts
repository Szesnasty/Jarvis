import type { ChatMessage, WsEvent } from '~/types'
import { useDuel } from '~/composables/useDuel'
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
  let _removeMessageListener: (() => void) | null = null
  let _removeReconnectListener: (() => void) | null = null

  const { isConnected, connect, send, onMessage, close, onReconnect, setSessionId } = useWebSocket()

  function _setError(msg: string, retryable = false): void {
    error.value = msg
    canRetry.value = retryable
    if (_errorClearTimer) clearTimeout(_errorClearTimer)
    _errorClearTimer = setTimeout(() => { error.value = ''; canRetry.value = false }, 8000)
  }

  const duel = useDuel()
  duel.bindSend(send)

  function _handleEvent(event: WsEvent): void {
    // Route duel events to the duel composable
    if ((event as any).type?.startsWith('duel_')) {
      duel.handleWsEvent(event as any)
      return
    }

    if (event.type === 'session_start') {
      sessionId.value = event.session_id
      setSessionId(event.session_id)
      try { sessionStorage.setItem('jarvis_session_id', event.session_id) } catch {}
      return
    }

    if (event.type === 'session_history') {
      // Restore chat history after reconnect/refresh (only if UI is empty)
      if (messages.value.length === 0 && Array.isArray(event.messages)) {
        messages.value = event.messages
      }
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

    if (event.type === 'memory_changed') {
      window.dispatchEvent(new CustomEvent('jarvis:memory-changed', { detail: event }))
      return
    }

    if (event.type === 'done') {
      if (currentResponse.value) {
        messages.value.push({
          role: 'assistant',
          content: currentResponse.value,
          model: event.model,
          provider: event.provider,
          timestamp: new Date().toISOString(),
        })
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
    if (event.type === 'disconnected') {
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
    // Clean up previous listeners if re-initializing (e.g. new session)
    if (_removeMessageListener) {
      _removeMessageListener()
      _removeMessageListener = null
    }
    if (_removeReconnectListener) {
      _removeReconnectListener()
      _removeReconnectListener = null
    }
    // Restore session ID from sessionStorage so page refreshes resume the same session
    const stored = (() => { try { return sessionStorage.getItem('jarvis_session_id') } catch { return null } })()
    if (stored && !sessionId.value) {
      sessionId.value = stored
    }
    // Always sync _lastSessionId — clears stale ID when starting a new session
    setSessionId(sessionId.value || '')
    connect(sessionId.value || undefined)
    _removeMessageListener = onMessage(_handleEvent)
    // When WS reconnects, clear transient error state.
    // The session_id is already passed via _lastSessionId in useWebSocket
    // so the backend will resume the same session.
    _removeReconnectListener = onReconnect(() => {
      error.value = ''
      canRetry.value = false
    })
  }

  function sendMessage(content: string, options?: { graphScope?: string }): void {
    if (!content.trim() || isLoading.value) return

    _lastContent = content.trim()
    messages.value.push({ role: 'user', content: _lastContent, timestamp: new Date().toISOString() })
    currentResponse.value = ''
    error.value = ''
    canRetry.value = false
    isLoading.value = true

    const payload: Record<string, string> = { type: 'message', content: _lastContent, session_id: sessionId.value }
    if (options?.graphScope) payload.graph_scope = options.graphScope

    // Attach provider + model + API key from browser storage
    const { activeProvider, activeKey, activeModel } = useApiKeys()
    if (activeKey.value) {
      payload.provider = activeProvider.value
      payload.api_key = activeKey.value
      payload.model = activeModel.value
    }

    const sent = send(payload)
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
    if (_errorClearTimer) {
      clearTimeout(_errorClearTimer)
      _errorClearTimer = null
    }
    if (_removeMessageListener) {
      _removeMessageListener()
      _removeMessageListener = null
    }
    if (_removeReconnectListener) {
      _removeReconnectListener()
      _removeReconnectListener = null
    }
    close()
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    messages,
    currentResponse,
    isLoading,
    toolActivity,
    error,
    canRetry,
    sessionId,
    isConnected,
    duel,
    init,
    sendMessage,
    retry,
    disconnect,
  }
}
