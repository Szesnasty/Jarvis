import type { WsEvent } from '~/types'

export function useWebSocket() {
  const isConnected = ref(false)
  const _ws = ref<WebSocket | null>(null)
  const _listeners = new Set<(event: WsEvent) => void>()
  let _heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let _reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let _reconnectAttempts = 0
  let _intentionalClose = false
  const _reconnectCallbacks = new Set<() => void>()

  function _getWsUrl(): string {
    const configured = useRuntimeConfig().public.backendWsUrl as string | undefined
    if (configured) return configured
    const loc = window.location
    const protocol = loc.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${loc.host}/api/chat/ws`
  }

  function onReconnect(cb: () => void): void {
    _reconnectCallbacks.add(cb)
  }

  function connect(): void {
    if (_ws.value && _ws.value.readyState === WebSocket.OPEN) return

    _intentionalClose = false
    const ws = new WebSocket(_getWsUrl())

    ws.onopen = () => {
      isConnected.value = true
      _reconnectAttempts = 0
      _heartbeatTimer = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 25_000)
      // Notify listeners that we reconnected (so they can re-init session etc)
      if (_reconnectAttempts > 0 || _ws.value !== ws) {
        for (const cb of _reconnectCallbacks) cb()
      }
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
      // Notify listeners of disconnect so UI can reset loading state
      for (const listener of _listeners) {
        listener({ type: 'disconnected' } as WsEvent)
      }
      if (!_intentionalClose) {
        _scheduleReconnect()
      }
    }

    ws.onerror = () => {
      isConnected.value = false
    }

    _ws.value = ws
  }

  function _scheduleReconnect(): void {
    _reconnectAttempts++
    // Exponential backoff: 1s, 2s, 4s, 8s, max 15s
    const delay = Math.min(1000 * Math.pow(2, _reconnectAttempts - 1), 15_000)
    _reconnectTimer = setTimeout(() => {
      connect()
    }, delay)
  }

  function _clearHeartbeat(): void {
    if (_heartbeatTimer) {
      clearInterval(_heartbeatTimer)
      _heartbeatTimer = null
    }
  }

  function send(data: Record<string, unknown>): boolean {
    if (!_ws.value || _ws.value.readyState !== WebSocket.OPEN) return false
    _ws.value.send(JSON.stringify(data))
    return true
  }

  function onMessage(listener: (event: WsEvent) => void): () => void {
    _listeners.add(listener)
    return () => _listeners.delete(listener)
  }

  function close(): void {
    _intentionalClose = true
    _clearHeartbeat()
    if (_reconnectTimer) {
      clearTimeout(_reconnectTimer)
      _reconnectTimer = null
    }
    _ws.value?.close()
    _ws.value = null
    isConnected.value = false
  }

  onUnmounted(() => {
    close()
  })

  return { isConnected, connect, send, onMessage, close, onReconnect }
}
