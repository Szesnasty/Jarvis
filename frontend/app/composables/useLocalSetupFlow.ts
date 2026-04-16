/**
 * State machine for local AI setup flow.
 * Shared between onboarding wizard and Settings page.
 */

export type LocalSetupState =
  | 'runtime_missing'
  | 'runtime_waiting'
  | 'runtime_ready'
  | 'model_selection'
  | 'model_downloading'
  | 'model_ready'
  | 'local_active'
  | 'error'

export type DetectedOS = 'macos' | 'windows' | 'linux'

export function useLocalSetupFlow() {
  const localModels = useLocalModels()
  const apiKeys = useApiKeys()

  const state = useState<LocalSetupState>('local-setup-state', () => 'runtime_missing')
  const errorMessage = useState<string>('local-setup-error', () => '')
  const downloadingModelId = useState<string | null>('local-setup-downloading', () => null)
  let _pollInterval: ReturnType<typeof setInterval> | null = null

  // Detect user's OS
  const detectedOS = useState<DetectedOS>('local-detected-os', () => {
    if (import.meta.client) {
      const ua = navigator.userAgent.toLowerCase()
      if (ua.includes('mac')) return 'macos'
      if (ua.includes('win')) return 'windows'
    }
    return 'linux'
  })

  const hardwareSummary = computed(() => {
    const hw = localModels.hardware.value
    if (!hw) return null
    const ram = `${hw.total_ram_gb.toFixed(0)} GB`
    let chip = ''
    if (hw.is_apple_silicon) chip = 'Apple Silicon'
    else if (hw.gpu_vendor) chip = `${hw.gpu_vendor} GPU`
    else chip = hw.os

    const tierLabel: Record<string, string> = {
      light: 'lightweight',
      balanced: 'medium',
      strong: 'medium to large',
      workstation: 'large',
    }
    const rec = tierLabel[hw.tier] ?? 'local'

    // Effective Ollama runtime context based on available RAM (per Ollama docs)
    const totalRam = hw.total_ram_gb
    const effectiveContext = totalRam >= 48 ? '256K' : totalRam >= 24 ? '32K' : '4K'

    return {
      ram,
      chip,
      label: chip ? `${ram} · ${chip}` : ram,
      recommendation: `Runs ${rec} local models comfortably`,
      effectiveContext,
    }
  })

  /** Determine initial state from runtime status */
  async function initialize(): Promise<void> {
    await localModels.refreshAll()
    _deriveState()
  }

  /** Derive state from current localModels data */
  function _deriveState(): void {
    if (localModels.activeModel.value) {
      state.value = 'local_active'
    } else if (localModels.installedModels.value.length > 0 && localModels.isOllamaReady()) {
      state.value = 'model_selection'
    } else if (localModels.isOllamaReady()) {
      state.value = 'model_selection'
    } else {
      state.value = 'runtime_missing'
    }
  }

  /** Open the official Ollama download for the detected OS */
  function openOllamaDownload(): void {
    const urls: Record<DetectedOS, string> = {
      macos: 'https://ollama.com/download/mac',
      windows: 'https://ollama.com/download/windows',
      linux: 'https://ollama.com/download/linux',
    }
    window.open(urls[detectedOS.value], '_blank', 'noopener')
    state.value = 'runtime_waiting'
    startPolling()
  }

  /** Start polling for Ollama on localhost */
  function startPolling(): void {
    if (_pollInterval) return
    _pollInterval = setInterval(async () => {
      await localModels.fetchRuntime()
      if (localModels.isOllamaReady()) {
        stopPolling()
        await localModels.fetchCatalog()
        state.value = 'model_selection'
      }
    }, 2500)
  }

  function stopPolling(): void {
    if (_pollInterval) {
      clearInterval(_pollInterval)
      _pollInterval = null
    }
  }

  /** Manual check again */
  async function checkAgain(): Promise<void> {
    await localModels.fetchRuntime()
    if (localModels.isOllamaReady()) {
      stopPolling()
      await localModels.fetchCatalog()
      state.value = 'model_selection'
    }
  }

  /** Download a model and track progress */
  async function downloadModel(modelId: string): Promise<boolean> {
    downloadingModelId.value = modelId
    state.value = 'model_downloading'
    errorMessage.value = ''

    await localModels.pullModel(modelId)

    const model = localModels.catalog.value.find(m => m.model_id === modelId)
    if (model?.installed) {
      await localModels.selectModel(modelId)
      // Sync selection into useApiKeys so ModelSelector reflects it immediately
      apiKeys.selectModel('ollama', model.litellm_model)
      downloadingModelId.value = null
      state.value = 'model_ready'
      return true
    } else {
      downloadingModelId.value = null
      state.value = 'model_selection'
      return false
    }
  }

  /** Cancel an in-progress download and return to model selection */
  function cancelDownload(): void {
    localModels.cancelPull()
    downloadingModelId.value = null
    state.value = 'model_selection'
  }

  /** Select an already-installed model */
  async function selectModel(modelId: string): Promise<void> {
    await localModels.selectModel(modelId)
    // Sync into useApiKeys so ModelSelector reflects it immediately
    const model = localModels.catalog.value.find(m => m.model_id === modelId)
    if (model) apiKeys.selectModel('ollama', model.litellm_model)
    state.value = 'model_ready'
  }

  /** Which wizard step is active (1-indexed) */
  const wizardStep = computed<1 | 2 | 3>(() => {
    switch (state.value) {
      case 'runtime_missing':
      case 'runtime_waiting':
        return 1
      case 'runtime_ready':
      case 'model_selection':
      case 'model_downloading':
        return 2
      case 'model_ready':
      case 'local_active':
        return 3
      case 'error':
        return 1
      default:
        return 1
    }
  })

  const isPolling = computed(() => _pollInterval !== null)

  function cleanup(): void {
    stopPolling()
  }

  return {
    state,
    errorMessage,
    downloadingModelId,
    detectedOS,
    hardwareSummary,
    wizardStep,
    isPolling,
    initialize,
    openOllamaDownload,
    startPolling,
    stopPolling,
    checkAgain,
    downloadModel,
    cancelDownload,
    selectModel,
    cleanup,
  }
}
