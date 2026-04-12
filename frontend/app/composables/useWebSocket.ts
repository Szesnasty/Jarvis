import type { WsEvent } from '~/types'

export function useWebSocket() {
  const isConnected = ref(false)
  const _ws = ref<WebSocket | null>(null)
  const _listeners = new Set<(event: WsEvent) => void>()
  let _heartbeatTimer: ReturnType<typeof setInterval> | null = null

  function _getWsUrl(): string {
    const configured = useRuntimeConfig().public.backendWsUrl as string | undefined
    if (configured) return configured
    const loc = window.location
    const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${loc.host}/api/chat/ws`
  }

  function connect(): void {
    if (_ws.value) return

    const ws = new WebSocket(_getWsUrl())

    ws.onopen = () => {
      isConnected.value = true
      _heartbeatTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 30_000)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WsEvent
        for (const listener of _listeners) {
          listener(data)
        }
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      isConnected.value = false
      _ws.value = null
      _clearHeartbeat()
    }

    ws.onerror = () => {
      isConnected.value = false
    }

    _ws.value = ws
  }

  function _clearHeartbeat(): void {
    if (_heartbeatTimer) {
      clearInterval(_heartbeatTimer)
      _heartbeatTimer = null
    }
  }

  function send(data: Record<string, unknown>): void {
    if (!_ws.value || _ws.value.readyState !== WebSocket.OPEN) return
    _ws.value.send(JSON.stringify(data))
  }

  function onMessage(listener: (event: WsEvent) => void): () => void {
    _listeners.add(listener)
    return () => _listeners.delete(listener)
  }

  function close(): void {
    _clearHeartbeat()
    _ws.value?.close()
    _ws.value = null
    isConnected.value = false
  }

  onUnmounted(() => {
    close()
  })

  return { isConnected, connect, send, onMessage, close }
}
