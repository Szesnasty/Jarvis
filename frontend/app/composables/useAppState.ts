import type { BackendStatus } from '~/types'

export function useAppState() {
  const isInitialized = useState<boolean>('isInitialized', () => false)
  const backendStatus = useState<BackendStatus>('backendStatus', () => 'unknown')

  async function checkHealth() {
    const { fetchHealth } = useApi()
    try {
      await fetchHealth()
      backendStatus.value = 'online'
    } catch {
      backendStatus.value = 'offline'
    }
  }

  return {
    isInitialized,
    backendStatus,
    checkHealth,
  }
}
