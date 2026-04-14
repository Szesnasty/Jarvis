import type { ProviderConfig, StoredKeyMeta } from '~/types'
import { PROVIDER_ICONS } from '~/composables/providerIcons'

/**
 * Model metadata for the selector UI.
 * `cost`: 1 = budget, 2 = standard, 3 = premium
 */
export interface ModelInfo {
  id: string
  label: string
  cost: 1 | 2 | 3
}

/** Full model catalog per provider. */
export const MODEL_CATALOG: Record<string, ModelInfo[]> = {
  anthropic: [
    { id: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4', cost: 2 },
    { id: 'claude-haiku-4-20250514', label: 'Claude Haiku 4.5', cost: 1 },
    { id: 'claude-opus-4-20250514', label: 'Claude Opus 4', cost: 3 },
  ],
  openai: [
    { id: 'gpt-4o', label: 'GPT-4o', cost: 2 },
    { id: 'gpt-4o-mini', label: 'GPT-4o mini', cost: 1 },
    { id: 'gpt-4-turbo', label: 'GPT-4 Turbo', cost: 3 },
    { id: 'gpt-4', label: 'GPT-4', cost: 3 },
    { id: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', cost: 1 },
    { id: 'o1', label: 'o1', cost: 3 },
    { id: 'o1-mini', label: 'o1 mini', cost: 2 },
    { id: 'o3-mini', label: 'o3 mini', cost: 2 },
  ],
  google: [
    { id: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro', cost: 2 },
    { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', cost: 1 },
    { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash', cost: 1 },
  ],
}

const PROVIDERS: ProviderConfig[] = [
  {
    id: 'anthropic',
    name: 'Anthropic',
    icon: PROVIDER_ICONS.anthropic,
    keyPrefix: 'sk-ant-',
    docsUrl: 'https://console.anthropic.com/settings/keys',
    models: MODEL_CATALOG.anthropic.map(m => m.id),
    color: '#D97706',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: PROVIDER_ICONS.openai,
    keyPrefix: 'sk-',
    docsUrl: 'https://platform.openai.com/api-keys',
    models: MODEL_CATALOG.openai.map(m => m.id),
    color: '#10A37F',
  },
  {
    id: 'google',
    name: 'Google AI',
    icon: PROVIDER_ICONS.google,
    keyPrefix: 'AI',
    docsUrl: 'https://aistudio.google.com/apikey',
    models: MODEL_CATALOG.google.map(m => m.id),
    color: '#4285F4',
  },
]

function _storageKey(providerId: string): string {
  return `jarvis_key_${providerId}`
}

function _metaKey(providerId: string): string {
  return `jarvis_key_meta_${providerId}`
}

function _readKey(providerId: string): string | null {
  try {
    // localStorage first (remembered keys), then sessionStorage
    const remembered = localStorage.getItem(_storageKey(providerId))
    if (remembered) return remembered
    return sessionStorage.getItem(_storageKey(providerId))
  } catch {
    return null
  }
}

function _readMeta(providerId: string): StoredKeyMeta | null {
  try {
    const raw = localStorage.getItem(_metaKey(providerId)) ?? sessionStorage.getItem(_metaKey(providerId))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const _DEFAULT_MODELS: Record<string, string> = {
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
  google: 'gemini-2.5-flash',
}

// Shared reactive state via useState (survives across components)
const _keyVersions = () => useState<number>('apiKeyVersion', () => 0)

export function useApiKeys() {
  const keyVersion = _keyVersions()
  const activeProvider = useState<string>('activeProvider', () => {
    // Default to first configured provider, or anthropic
    for (const p of PROVIDERS) {
      if (_readKey(p.id)) return p.id
    }
    return 'anthropic'
  })

  const activeModel = useState<string>('activeModel', () => {
    try {
      const saved = localStorage.getItem('jarvis_active_model')
      const savedProvider = localStorage.getItem('jarvis_active_provider')
      // Verify saved model belongs to a provider with a configured key
      if (saved && savedProvider && _readKey(savedProvider)) {
        const catalog = MODEL_CATALOG[savedProvider]
        if (catalog?.some(m => m.id === saved)) return saved
      }
    } catch { /* ignore */ }
    // Fallback: default model for the active provider
    const prov = activeProvider.value
    return _DEFAULT_MODELS[prov] ?? 'claude-sonnet-4-20250514'
  })

  function getKey(providerId: string): string | null {
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    keyVersion.value // reactive dependency
    return _readKey(providerId)
  }

  function setKey(providerId: string, key: string, remember: boolean): void {
    const meta: StoredKeyMeta = { remember, addedAt: new Date().toISOString() }
    try {
      // Clear both storages first
      localStorage.removeItem(_storageKey(providerId))
      sessionStorage.removeItem(_storageKey(providerId))
      localStorage.removeItem(_metaKey(providerId))
      sessionStorage.removeItem(_metaKey(providerId))

      if (remember) {
        localStorage.setItem(_storageKey(providerId), key)
        localStorage.setItem(_metaKey(providerId), JSON.stringify(meta))
      } else {
        sessionStorage.setItem(_storageKey(providerId), key)
        sessionStorage.setItem(_metaKey(providerId), JSON.stringify(meta))
      }
    } catch {
      // Storage full or blocked — fail silently
    }
    keyVersion.value++
    // Auto-set active provider if none configured yet
    if (!_readKey(activeProvider.value)) {
      activeProvider.value = providerId
    }
  }

  function removeKey(providerId: string): void {
    try {
      localStorage.removeItem(_storageKey(providerId))
      sessionStorage.removeItem(_storageKey(providerId))
      localStorage.removeItem(_metaKey(providerId))
      sessionStorage.removeItem(_metaKey(providerId))
    } catch {
      // ignore
    }
    keyVersion.value++
    // If we removed the active provider, switch to first available
    if (activeProvider.value === providerId) {
      const next = PROVIDERS.find(p => _readKey(p.id) && p.id !== providerId)
      activeProvider.value = next?.id ?? 'anthropic'
    }
  }

  function isConfigured(providerId: string): boolean {
    return !!getKey(providerId)
  }

  function getMaskedKey(providerId: string): string {
    const key = getKey(providerId)
    if (!key) return ''
    const prefix = PROVIDERS.find(p => p.id === providerId)?.keyPrefix ?? ''
    return prefix + '****'
  }

  function isRemembered(providerId: string): boolean {
    const meta = _readMeta(providerId)
    return meta?.remember ?? false
  }

  function hasAnyKey(): boolean {
    return PROVIDERS.some(p => isConfigured(p.id))
  }

  function selectModel(providerId: string, modelId: string): void {
    const catalog = MODEL_CATALOG[providerId]
    if (!catalog?.some(m => m.id === modelId)) return
    activeProvider.value = providerId
    activeModel.value = modelId
    try {
      localStorage.setItem('jarvis_active_model', modelId)
      localStorage.setItem('jarvis_active_provider', providerId)
    } catch { /* ignore */ }
  }

  function getActiveModelInfo(): ModelInfo | undefined {
    const catalog = MODEL_CATALOG[activeProvider.value]
    return catalog?.find(m => m.id === activeModel.value)
  }

  /** Configured providers with at least one model available. */
  function configuredProviders(): ProviderConfig[] {
    return PROVIDERS.filter(p => isConfigured(p.id))
  }

  const activeKey = computed(() => getKey(activeProvider.value))

  return {
    providers: PROVIDERS,
    getKey,
    setKey,
    removeKey,
    isConfigured,
    getMaskedKey,
    isRemembered,
    hasAnyKey,
    activeProvider,
    activeModel,
    activeKey,
    selectModel,
    getActiveModelInfo,
    configuredProviders,
  }
}
