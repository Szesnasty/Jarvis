import { ref } from 'vue'

export type GeneralSettings = {
  workspace_path: string
  api_key_set: boolean
  key_storage: string
  voice: { auto_speak: string | boolean; tts_voice: string }
}

export function useGeneralSettings() {
  const loaded = ref(false)
  const workspacePath = ref('')
  const serverKeyConfigured = ref(false)
  const keyStorage = ref('')
  const autoSpeak = ref(false)
  const error = ref('')

  async function load() {
    try {
      const resp = await $fetch<GeneralSettings>('/api/settings')
      workspacePath.value = resp.workspace_path
      serverKeyConfigured.value = resp.api_key_set
      keyStorage.value = resp.key_storage
      autoSpeak.value = resp.voice.auto_speak === 'true' || resp.voice.auto_speak === true
      loaded.value = true
    } catch {
      loaded.value = true
      error.value = 'Failed to load settings'
    }
  }

  async function updateVoice(): Promise<void> {
    try {
      await $fetch('/api/settings/voice', {
        method: 'PATCH',
        body: { auto_speak: String(autoSpeak.value) },
      })
    } catch { /* ignore */ }
  }

  async function reindexMemory(): Promise<number | null> {
    try {
      const resp = await $fetch<{ indexed: number }>('/api/memory/reindex', { method: 'POST' })
      return resp.indexed
    } catch { return null }
  }

  async function rebuildGraph(): Promise<boolean> {
    try {
      await $fetch('/api/graph/rebuild', { method: 'POST' })
      return true
    } catch { return false }
  }

  return {
    loaded, workspacePath, serverKeyConfigured, keyStorage, autoSpeak, error,
    load, updateVoice, reindexMemory, rebuildGraph,
  }
}
