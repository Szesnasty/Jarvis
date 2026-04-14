# Step 18a — Multi-Provider API Keys: Frontend (Storage, Settings UI)

> **Goal**: Replace the single Anthropic API key workflow with a multi-provider
> key management system. Keys are stored **in the browser only** (sessionStorage
> by default, localStorage with opt-in). The Settings page gets a redesigned
> provider card UI inspired by ai-protector.

**Status**: ⬜ Not started
**Depends on**: None (can start independently, but 18b must follow before chat works with non-Anthropic models)

---

## Core Principles

1. **Keys never leave the browser** — stored in sessionStorage (default) or localStorage ("Remember on this device"). Sent per-request in HTTP headers or WS messages.
2. **Backend never stores keys** — pass-through only. Backend receives key in request, uses it, discards it. No keyring, no file, no env var for multi-provider keys.
3. **Anthropic migration** — existing keyring/file-stored Anthropic key continues to work as fallback. New flow is additive.
4. **Provider-agnostic UI** — adding a new provider = adding a config entry, not new components.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `useApiKeys.ts` | Composable: store/retrieve/remove keys, "remember" flag, provider registry |
| Settings page redesign | Provider cards with status, Add Key modal, key protection info |
| Key passing | Attach active provider's key to WS messages and HTTP requests |
| Provider registry | Static config for supported providers (name, icon, key prefix, docs URL) |

**What this step does NOT cover** (deferred to 18b):
- LiteLLM backend integration
- Model selection
- Backend multi-provider routing

---

## File Structure

```
frontend/
  app/
    composables/
      useApiKeys.ts           # NEW — key storage + provider state
    components/
      ProviderCard.vue        # NEW — single provider row
      AddKeyModal.vue         # NEW — modal for adding/replacing a key
      KeyProtectionInfo.vue   # NEW — "How we protect your keys" info box
    pages/
      settings.vue            # MODIFY — replace API Key section with provider cards
    services/
      api.ts                  # MODIFY — attach key header to requests
```

---

## Provider Registry

Static config — no backend call needed.

```typescript
interface ProviderConfig {
  id: string
  name: string
  icon: string                // emoji or SVG component name
  keyPrefix: string           // for validation hint (e.g. "sk-ant-")
  docsUrl: string             // link to "get your key" page
  models: string[]            // available models (used in step 18c)
  color: string               // accent color for card
}

const PROVIDERS: ProviderConfig[] = [
  {
    id: "anthropic",
    name: "Anthropic",
    icon: "🤖",
    keyPrefix: "sk-ant-",
    docsUrl: "https://console.anthropic.com/settings/keys",
    models: ["claude-sonnet-4-20250514", "claude-haiku-4-20250514"],
    color: "#D97706",
  },
  {
    id: "openai",
    name: "OpenAI",
    icon: "✨",
    keyPrefix: "sk-",
    docsUrl: "https://platform.openai.com/api-keys",
    models: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    color: "#10A37F",
  },
  {
    id: "google",
    name: "Google AI",
    icon: "G",
    keyPrefix: "AI",
    docsUrl: "https://aistudio.google.com/apikey",
    models: ["gemini-2.5-flash", "gemini-2.5-pro"],
    color: "#4285F4",
  },
]
```

---

## Composable: `useApiKeys.ts`

```typescript
interface StoredKey {
  key: string
  remember: boolean           // true = localStorage, false = sessionStorage
  addedAt: string             // ISO timestamp
}

interface UseApiKeys {
  providers: ProviderConfig[]
  getKey(providerId: string): string | null
  setKey(providerId: string, key: string, remember: boolean): void
  removeKey(providerId: string): void
  isConfigured(providerId: string): boolean
  getMaskedKey(providerId: string): string   // "sk-ant-****"
  isRemembered(providerId: string): boolean
  activeProvider: Ref<string>                // currently selected provider ID
  activeKey: ComputedRef<string | null>      // key for active provider
}
```

### Storage Strategy

```
sessionStorage key: "jarvis_key_{providerId}"
localStorage key:   "jarvis_key_{providerId}"
metadata:           "jarvis_key_meta_{providerId}" → { remember: bool, addedAt: string }
```

- **Default**: sessionStorage (cleared on tab close)
- **"Remember on this device"**: copies to localStorage instead
- On load: check localStorage first, then sessionStorage
- `removeKey()`: clears both storages

### Masking

```typescript
function getMaskedKey(providerId: string): string {
  const key = getKey(providerId)
  if (!key) return ""
  const prefix = PROVIDERS.find(p => p.id === providerId)?.keyPrefix ?? ""
  return prefix + "****"
}
```

---

## Settings Page Redesign

### Layout

```
┌─────────────────────────────────────────────────┐
│  Settings                                        │
├─────────────────────────────────────────────────┤
│                                                  │
│  AI Providers           🔒 Keys handled locally  │
│                                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ ℹ️  How we protect your keys             │     │
│  │                                          │     │
│  │ • Keys are stored in your browser only   │     │
│  │ • Never sent to our server or logged     │     │
│  │ • Passed directly to the AI provider     │     │
│  │ • Session keys clear when you close tab  │     │
│  └─────────────────────────────────────────┘     │
│                                                  │
│  ┌─────────────────────────────────────────┐     │
│  │ 🤖  Anthropic        ✅ Configured       │     │
│  │     sk-ant-****      this session only   │     │
│  │                              [Remove]    │     │
│  ├─────────────────────────────────────────┤     │
│  │ ✨  OpenAI           [Add Key]           │     │
│  │     No key added                         │     │
│  ├─────────────────────────────────────────┤     │
│  │ G   Google AI        [Add Key]           │     │
│  │     No key added                         │     │
│  └─────────────────────────────────────────┘     │
│                                                  │
│  Workspace                                       │
│  ~/Jarvis                                        │
│                                                  │
│  Voice Settings                                  │
│  ...                                             │
│                                                  │
│  Maintenance                                     │
│  ...                                             │
│                                                  │
│  Token Usage & Budget                            │
│  ...                                             │
└─────────────────────────────────────────────────┘
```

### Provider Card States

**1. No key added:**
```
┌───────────────────────────────────────┐
│ ✨  OpenAI                  [Add Key]  │
│     No key added                       │
└───────────────────────────────────────┘
```
- Muted styling, "Add Key" button (outline style)

**2. Configured (session only):**
```
┌───────────────────────────────────────┐
│ 🤖  Anthropic       ✅ Configured      │
│     sk-ant-****     this session only  │
│                             [Remove]   │
└───────────────────────────────────────┘
```
- Green "Configured" badge
- Masked key display
- "this session only" indicator (if not remembered)
- "Remove" button (danger style)

**3. Configured (remembered):**
```
┌───────────────────────────────────────┐
│ 🤖  Anthropic       ✅ Configured      │
│     sk-ant-****     remembered         │
│                             [Remove]   │
└───────────────────────────────────────┘
```
- Same as above but "remembered" instead of "this session only"

---

## Add Key Modal — `AddKeyModal.vue`

```
┌─────────────────────────────────────────────┐
│  🤖  Add Anthropic Key                       │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ ℹ️  Stored locally in your browser.    │  │
│  │    Never sent to our server.           │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  API Key                                     │
│  ┌────────────────────────────────────────┐  │
│  │ sk-ant-...                       👁️    │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ☐ Remember on this device                   │
│    Key will persist across browser sessions  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ This key is used to call Anthropic's   │  │
│  │ API directly from your browser.        │  │
│  │ Get yours at console.anthropic.com →   │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  [Cancel]                      [Save Key]    │
└─────────────────────────────────────────────┘
```

### Props & Events

```typescript
props: {
  provider: ProviderConfig     // which provider to add key for
  show: boolean
}

emits: {
  close: []
  saved: [providerId: string]
}
```

### Behavior

- `type="password"` input with toggle visibility (👁️ button)
- Key prefix validation: warn (not block) if key doesn't start with expected prefix
- "Remember on this device" checkbox — unchecked by default
- On save: call `useApiKeys().setKey(provider.id, key, remember)`
- Close modal, emit `saved`
- Focus trap inside modal (a11y)
- Escape key closes

---

## Key Passing — Integration with Chat & API

### WebSocket Messages

Currently chat sends:
```json
{ "type": "message", "content": "..." }
```

New format adds key header:
```json
{
  "type": "message",
  "content": "...",
  "provider": "anthropic",
  "api_key": "sk-ant-..."
}
```

Modify `useChat.ts` → before sending any message, attach `provider` and `api_key` from `useApiKeys()`.

### HTTP Requests

For REST calls that need AI (future), add header:
```
X-Provider: anthropic
X-Api-Key: sk-ant-...
```

Modify `api.ts` → interceptor adds headers if `useApiKeys().activeKey` is set.

---

## Migration from Current System

### Phase 1 (this step): Hybrid mode
- New provider cards UI in Settings
- If user has existing keyring/file Anthropic key, show it as "Configured (server-side)"
- New keys added via UI stored in browser
- WS messages include `api_key` field — backend uses it if present, falls back to server-stored key
- Backend endpoint `GET /api/settings` adds `server_key_configured: true` flag

### Phase 2 (future): Full browser-only
- Remove keyring/file storage
- All keys browser-only
- Backend has zero key storage

---

## Backward Compatibility

- **Existing Anthropic key** in keyring/file still works
- **WS handler** tries `msg.api_key` first, then `get_api_key()` fallback
- **Settings UI** shows both: server-stored key (if any) + browser-stored keys
- No breaking changes to onboarding flow (step 03 still stores key server-side for now)

---

## Acceptance Criteria

1. Provider cards render for all 3 providers
2. "Add Key" opens modal, saves key to sessionStorage
3. "Remember on this device" saves to localStorage instead
4. Configured providers show green badge + masked key
5. "Remove" clears key from both storages
6. Chat WS messages include `provider` + `api_key` fields
7. Backend accepts `api_key` from WS message (fall back to stored key)
8. Existing Anthropic keyring/file key still works
9. "Keys handled locally" badge visible
10. "How we protect your keys" info box renders

---

## Tests

### Frontend (Vitest)
- `useApiKeys` — set/get/remove keys, sessionStorage vs localStorage, masking
- `ProviderCard` — renders all 3 states (no key, configured session, configured remembered)
- `AddKeyModal` — input validation, save flow, cancel/escape

### Backend (pytest)
- `test_chat_ws.py` — verify WS handler accepts `api_key` from message
- `test_settings_api.py` — `server_key_configured` flag in response

---

## Security Notes

- Keys in sessionStorage/localStorage are accessible to any JS on the page → acceptable for a local-only app with no third-party scripts
- Never log keys (not even masked) in console
- Clear key from JS variable after passing to fetch/WS (don't hold in long-lived state beyond the composable ref)
- CSP headers should prevent script injection (existing Nuxt config)
