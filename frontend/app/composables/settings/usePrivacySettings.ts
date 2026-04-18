import { ref } from 'vue'

export type PrivacyState = {
  offline_mode: boolean
  offline_mode_locked: boolean
  web_search_enabled: boolean
  url_ingest_enabled: boolean
  cloud_providers_enabled: boolean
}

export function usePrivacySettings() {
  const privacy = ref<PrivacyState | null>(null)
  const saving = ref(false)
  const error = ref('')
  const lastChange = ref<{ key: keyof PrivacyState; value: boolean } | null>(null)

  async function load() {
    try {
      privacy.value = await $fetch<PrivacyState>('/api/settings/privacy')
    } catch {
      error.value = 'Failed to load privacy settings'
    }
  }

  async function set(key: keyof PrivacyState, value: boolean) {
    saving.value = true
    error.value = ''
    try {
      privacy.value = await $fetch<PrivacyState>('/api/settings/privacy', {
        method: 'PATCH',
        body: { [key]: value },
      })
      lastChange.value = { key, value }
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string } }
      error.value = err?.data?.detail ?? 'Failed to update privacy settings'
      await load()
    } finally {
      saving.value = false
    }
  }

  return { privacy, saving, error, lastChange, load, set }
}
