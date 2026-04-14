import type { ProviderConfig, StoredKeyMeta } from '~/types'

const PROVIDERS: ProviderConfig[] = [
  {
    id: 'anthropic',
    name: 'Anthropic',
    icon: '🤖',
    keyPrefix: 'sk-ant-',
    docsUrl: 'https://console.anthropic.com/settings/keys',
    models: ['claude-sonnet-4-20250514', 'claude-haiku-4-20250514'],
    color: '#D97706',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: '✨',
    keyPrefix: 'sk-',
    docsUrl: 'https://platform.openai.com/api-keys',
    models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
    color: '#10A37F',
  },
  {
    id: 'google',
    name: 'Google AI',
    icon: 'G',
    keyPrefix: 'AI',
    docsUrl: 'https://aistudio.google.com/apikey',
    models: ['gemini-2.5-flash', 'gemini-2.5-pro'],
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
    activeKey,
  }
}
