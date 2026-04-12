import type { SpecialistSummary, SpecialistDetail } from '~/types'
import { useApi } from '~/composables/useApi'

export function useSpecialists() {
  const specialists = useState<SpecialistSummary[]>('specialists', () => [])
  const activeSpecialist = useState<SpecialistDetail | null>('activeSpecialist', () => null)
  const loading = useState<boolean>('specialistsLoading', () => false)
  const api = useApi()

  async function load() {
    loading.value = true
    try {
      specialists.value = await api.fetchSpecialists()
      activeSpecialist.value = await api.fetchActiveSpecialist()
    } finally {
      loading.value = false
    }
  }

  async function activate(id: string) {
    await api.activateSpecialist(id)
    activeSpecialist.value = await api.fetchSpecialist(id)
  }

  async function deactivate() {
    await api.deactivateSpecialist()
    activeSpecialist.value = null
  }

  async function remove(id: string) {
    await api.deleteSpecialist(id)
    specialists.value = specialists.value.filter(s => s.id !== id)
    if (activeSpecialist.value?.id === id) {
      activeSpecialist.value = null
    }
  }

  return { specialists, activeSpecialist, loading, load, activate, deactivate, remove }
}
