# API Key Management

> **Status**: Step 18a implemented  
> **Last updated**: 2026-04-16

## Summary

Browser-side multi-provider API key management. Keys are stored in the browser (sessionStorage or localStorage) and attached to each WebSocket message, so the backend never persists them. Supports Anthropic, OpenAI, and Google AI providers.

## How It Works

### Key Storage Strategy

1. **Default**: `sessionStorage` — key lives only in the current tab; lost on close.
2. **"Remember on this device"**: `localStorage` — persists across sessions.
3. **On read**: localStorage is checked first, then sessionStorage (allows a "remembered" key to survive tab reloads).

Storage keys follow the pattern:
- `jarvis_key_{providerId}` — the raw API key
- `jarvis_key_meta_{providerId}` — JSON metadata (`{ remember: boolean, addedAt: string }`)

### Provider Registry

The `PROVIDERS` array in `useApiKeys.ts` defines each supported provider:

| Provider | ID | Key Prefix | Color |
|----------|-----|------------|-------|
| Anthropic | `anthropic` | `sk-ant-` | `#D97706` |
| OpenAI | `openai` | `sk-` | `#10A37F` |
| Google AI | `google` | `AI` | `#4285F4` |

Prefix validation shows a warning but does not block key entry.

### WebSocket Integration

`useChat.ts` reads `activeProvider` and `activeKey` from `useApiKeys()` and attaches them as `provider` and `api_key` fields on every WS message payload.

### Backend Key Resolution

`chat.py` extracts `client_api_key = data.get("api_key")` from each message. Resolution order:
1. Client-provided key (from browser)
2. Server-configured key (from `config.json` / env var)

If the client key changes between messages, `ClaudeService` is recreated with the new key.

## Key Files

| File | Role |
|------|------|
| `frontend/app/composables/useApiKeys.ts` | Core composable — storage, provider registry, reactive state |
| `frontend/app/components/ProviderCard.vue` | Provider row: icon, status badge, masked key, add/remove |
| `frontend/app/components/AddKeyModal.vue` | Modal for entering/replacing a key |
| `frontend/app/components/KeyProtectionInfo.vue` | Reusable "how we protect your keys" info box |
| `frontend/app/types/index.ts` | `ProviderConfig` and `StoredKeyMeta` interfaces |
| `frontend/app/pages/settings.vue` | Settings page — AI Providers section |
| `frontend/app/composables/useChat.ts` | Attaches provider + key to WS payloads |
| `backend/routers/chat.py` | Receives client key, falls back to server key |

## Composable API

```ts
const {
  providers,          // ProviderConfig[] — static registry
  getKey,             // (id: string) => string | null
  setKey,             // (id: string, key: string, remember: boolean) => void
  removeKey,          // (id: string) => void
  isConfigured,       // (id: string) => boolean
  getMaskedKey,       // (id: string) => string | null  (e.g. "sk-ant-•••xyz")
  isRemembered,       // (id: string) => boolean
  hasAnyKey,          // () => boolean
  activeProvider,     // Ref<string> — selected provider ID
  activeKey,          // ComputedRef<string | null> — key for activeProvider
} = useApiKeys()
```

## Tests

- **Frontend**: `tests/composables/useApiKeys.test.ts` — 11 tests covering get/set/remove, storage strategies, masking, remember flag.
- **Backend**: `test_chat_ws.py` — 2 tests for client key pass-through and server key fallback.
