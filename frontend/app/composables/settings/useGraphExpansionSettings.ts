import { ref } from 'vue'

export interface GraphExpansionConfig {
  use_related: boolean
  use_part_of: boolean
  use_suggested_strong: boolean
}

const DEFAULT_CONFIG: GraphExpansionConfig = {
  use_related: true,
  use_part_of: true,
  use_suggested_strong: false,
}

export function useGraphExpansionSettings() {
  const config = ref<GraphExpansionConfig>({ ...DEFAULT_CONFIG })
  const saving = ref(false)
  const error = ref('')

  async function load() {
    try {
      const data = await $fetch<{ graph_expansion: GraphExpansionConfig }>('/api/settings/retrieval')
      config.value = { ...DEFAULT_CONFIG, ...data.graph_expansion }
    } catch {
      error.value = 'Failed to load retrieval settings'
    }
  }

  async function set(key: keyof GraphExpansionConfig, value: boolean) {
    saving.value = true
    error.value = ''
    try {
      const data = await $fetch<{ graph_expansion: GraphExpansionConfig }>('/api/settings/retrieval', {
        method: 'PATCH',
        body: { graph_expansion: { [key]: value } },
      })
      config.value = { ...DEFAULT_CONFIG, ...data.graph_expansion }
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string } }
      error.value = err?.data?.detail ?? 'Failed to update retrieval settings'
      await load()
    } finally {
      saving.value = false
    }
  }

  return { config, saving, error, load, set }
}
