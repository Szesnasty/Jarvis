import type { BackendStatus } from '~/types'

export function useAppState() {
  const isInitialized = useState<boolean>('isInitialized', () => false)
  const backendStatus = useState<BackendStatus>('backendStatus', () => 'unknown')
  const chatActive = useState<boolean>('chatActive', () => false)

  async function checkHealth() {
    const { fetchHealth } = useApi()
    try {
      await fetchHealth()
      backendStatus.value = 'online'
    } catch {
      backendStatus.value = 'offline'
    }
  }

  async function checkWorkspaceStatus() {
    const { fetchWorkspaceStatus } = useApi()
    try {
      const data = await fetchWorkspaceStatus()
      isInitialized.value = data.initialized
    } catch {
      isInitialized.value = false
    }
  }

  return {
    isInitialized,
    backendStatus,
    chatActive,
    checkHealth,
    checkWorkspaceStatus,
  }
}
