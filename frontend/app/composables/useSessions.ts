import type { SessionMetadata, SessionDetail } from '~/types'
import { useApi } from '~/composables/useApi'

export function useSessions() {
  const sessions = ref<SessionMetadata[]>([])
  const activeSessionId = ref<string | null>(null)
  const { fetchSessions, fetchSession, resumeSession } = useApi()

  async function loadSessions(): Promise<void> {
    sessions.value = await fetchSessions()
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

  function clearActive(): void {
    activeSessionId.value = null
  }

  return { sessions, activeSessionId, loadSessions, selectSession, resume, clearActive }
}
