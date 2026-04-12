import type { ChatMessage, WsEvent } from '~/types'

export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const currentResponse = ref('')
  const isLoading = ref(false)
  const toolActivity = ref('')
  const error = ref('')
  const sessionId = ref('')

  const { isConnected, connect, send, onMessage, close } = useWebSocket()

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
      error.value = event.content
      isLoading.value = false
      toolActivity.value = ''
      return
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
  }

  function sendMessage(content: string): void {
    if (!content.trim() || isLoading.value) return

    messages.value.push({ role: 'user', content: content.trim() })
    currentResponse.value = ''
    error.value = ''
    isLoading.value = true

    send({ type: 'message', content: content.trim(), session_id: sessionId.value })
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
    sessionId,
    isConnected,
    init,
    sendMessage,
    disconnect,
  }
}
