import type { HardwareProfile, RuntimeStatus, ModelRecommendation, PullProgress } from '~/types'

const OLLAMA_BASE_URL_KEY = 'jarvis-ollama-base-url'
const DEFAULT_BASE_URL = 'http://localhost:11434'

function _readBaseUrl(): string {
  try {
    return localStorage.getItem(OLLAMA_BASE_URL_KEY) ?? DEFAULT_BASE_URL
  } catch {
    return DEFAULT_BASE_URL
  }
}

export function useLocalModels() {
  const hardware = useState<HardwareProfile | null>('local-hardware', () => null)
  const runtime = useState<RuntimeStatus | null>('local-runtime', () => null)
  const catalog = useState<ModelRecommendation[]>('local-catalog', () => [])
  const pulling = useState<string | null>('local-pulling', () => null)
  const pullProgress = useState<PullProgress | null>('local-pull-progress', () => null)
  const loading = useState<boolean>('local-loading', () => false)
  const error = useState<string | null>('local-error', () => null)
  const baseUrl = useState<string>('local-base-url', () => _readBaseUrl())
  const ollamaDown = useState<boolean>('local-ollama-down', () => false)
  let _healthInterval: ReturnType<typeof setInterval> | null = null

  async function fetchHardware(): Promise<void> {
    try {
      hardware.value = await $fetch<HardwareProfile>('/api/local/hardware')
    } catch (e: unknown) {
      error.value = 'Failed to fetch hardware info'
    }
  }

  async function fetchRuntime(): Promise<void> {
    try {
      runtime.value = await $fetch<RuntimeStatus>('/api/local/runtime', {
        params: { base_url: baseUrl.value },
      })
    } catch (e: unknown) {
      runtime.value = {
        runtime: 'ollama',
        installed: false,
        running: false,
        base_url: baseUrl.value,
        reachable: false,
      }
    }
  }

  async function fetchCatalog(): Promise<void> {
    try {
      catalog.value = await $fetch<ModelRecommendation[]>('/api/local/models/catalog', {
        params: { base_url: baseUrl.value },
      })
    } catch (e: unknown) {
      error.value = 'Failed to fetch model catalog'
    }
  }

  async function refreshAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await fetchHardware()
      await fetchRuntime()
      // Always fetch catalog — models are scored by hardware even without Ollama
      await fetchCatalog()
    } finally {
      loading.value = false
    }
  }

  async function pullModel(modelId: string): Promise<void> {
    const model = catalog.value.find(m => m.model_id === modelId)
    if (!model) return

    pulling.value = modelId
    pullProgress.value = { status: 'starting' }
    error.value = null

    try {
      const response = await fetch('/api/local/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: model.ollama_model,
          base_url: baseUrl.value,
        }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`Pull failed: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value)
        for (const line of text.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              pullProgress.value = data
              if (data.status === 'done' || data.status === 'success') {
                pulling.value = null
                pullProgress.value = null
                await fetchCatalog()
              }
            } catch {
              // ignore malformed SSE lines
            }
          }
        }
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Pull failed'
    } finally {
      if (pulling.value === modelId) {
        pulling.value = null
        pullProgress.value = null
      }
    }
  }

  async function selectModel(modelId: string): Promise<void> {
    const model = catalog.value.find(m => m.model_id === modelId)
    if (!model) return

    try {
      await $fetch('/api/local/models/select', {
        method: 'POST',
        body: {
          model_id: model.model_id,
          litellm_model: model.litellm_model,
          base_url: baseUrl.value,
        },
      })
      await fetchCatalog()
    } catch (e: unknown) {
      error.value = 'Failed to select model'
    }
  }

  async function deleteModel(ollamaModel: string): Promise<void> {
    try {
      await $fetch(`/api/local/models/${encodeURIComponent(ollamaModel)}`, {
        method: 'DELETE',
        params: { base_url: baseUrl.value },
      })
      await fetchCatalog()
    } catch (e: unknown) {
      error.value = 'Failed to delete model'
    }
  }

  function isOllamaReady(): boolean {
    return !!(runtime.value?.installed && runtime.value?.running)
  }

  function startHealthPolling(intervalMs = 30_000): void {
    stopHealthPolling()
    _healthInterval = setInterval(async () => {
      await fetchRuntime()
      ollamaDown.value = !(runtime.value?.reachable)
    }, intervalMs)
  }

  function stopHealthPolling(): void {
    if (_healthInterval) {
      clearInterval(_healthInterval)
      _healthInterval = null
    }
  }

  async function warmUpModel(ollamaModel: string): Promise<void> {
    try {
      await $fetch('/api/local/models/warm-up', {
        method: 'POST',
        body: { model: ollamaModel, base_url: baseUrl.value },
      })
    } catch {
      // Fire-and-forget; ignore errors
    }
  }

  function setBaseUrl(url: string): void {
    baseUrl.value = url
    try {
      localStorage.setItem(OLLAMA_BASE_URL_KEY, url)
    } catch { /* ignore */ }
  }

  const recommendedModels = computed(() =>
    catalog.value.filter(m => m.recommended),
  )

  const installedModels = computed(() =>
    catalog.value.filter(m => m.installed),
  )

  const activeModel = computed(() =>
    catalog.value.find(m => m.active),
  )

  return {
    hardware,
    runtime,
    catalog,
    pulling,
    pullProgress,
    loading,
    error,
    baseUrl,
    ollamaDown,
    fetchHardware,
    fetchRuntime,
    fetchCatalog,
    refreshAll,
    pullModel,
    selectModel,
    deleteModel,
    isOllamaReady,
    startHealthPolling,
    stopHealthPolling,
    warmUpModel,
    setBaseUrl,
    recommendedModels,
    installedModels,
    activeModel,
  }
}
