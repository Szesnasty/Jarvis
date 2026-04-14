import type { SessionMetadata, SessionDetail } from '~/types'
import { useApi } from '~/composables/useApi'

export function useSessions() {
  const sessions = ref<SessionMetadata[]>([])
  const activeSessionId = ref<string | null>(null)
  const loading = ref(false)
  const { fetchSessions, fetchSession, resumeSession, deleteSession: apiDeleteSession } = useApi()

  async function loadSessions(): Promise<void> {
    loading.value = true
    try {
      sessions.value = await fetchSessions()
    } finally {
      loading.value = false
    }
  }

  async function selectSession(sessionId: string): Promise<SessionDetail> {
    const detail = await fetchSession(sessionId)
    activeSessionId.value = sessionId
    return detail
  }

  async function resume(sessionId: string): Promise<void> {
    await resumeSession(sessionId)
    activeSessionId.value = sessionId
  }

  async function removeSession(sessionId: string): Promise<void> {
    await apiDeleteSession(sessionId)
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    if (activeSessionId.value === sessionId) {
      activeSessionId.value = null
    }
  }

  function clearActive(): void {
    activeSessionId.value = null
  }

  return { sessions, activeSessionId, loading, loadSessions, selectSession, resume, removeSession, clearActive }
}
