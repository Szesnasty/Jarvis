import { useApi } from '~/composables/useApi'

export function usePreferences() {
  const preferences = ref<Record<string, string>>({})
  const { fetchPreferences, setPreference: apiSetPreference } = useApi()

  async function loadPreferences(): Promise<void> {
    preferences.value = await fetchPreferences()
  }

  async function setPreference(key: string, value: string): Promise<void> {
    // Optimistic update
    preferences.value = { ...preferences.value, [key]: value }
    try {
      preferences.value = await apiSetPreference(key, value)
    } catch {
      // Revert on failure
      await loadPreferences()
    }
  }

  return { preferences, loadPreferences, setPreference }
}
