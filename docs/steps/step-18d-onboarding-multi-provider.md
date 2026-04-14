# Step 18d — Onboarding Redesign: Multi-Provider Welcome Flow

> **Goal**: Redesign the onboarding page to support multi-provider key setup.
> First-time users see provider cards with key security info, can add keys for
> any provider (at least one required), and create the workspace.

**Status**: ⬜ Not started
**Depends on**: Step 18a (useApiKeys composable, ProviderCard, AddKeyModal, KeyProtectionInfo)

---

## Why a Separate Step

Step 18a adds provider cards to **Settings** (for returning users).
This step redesigns **Onboarding** (for first-time users).

Key differences from Settings:
- At least **one provider key required** before "Create Workspace" is enabled
- Full-screen welcome layout (not a settings section)
- Prominent security explanation (trust must be established upfront)
- Workspace creation still happens (folder structure + SQLite)
- API key is **no longer sent to backend** during onboarding — stored in browser only

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Onboarding redesign | Multi-step: welcome → add keys → create workspace |
| Provider cards in onboarding | Reuse `ProviderCard.vue` + `AddKeyModal.vue` from 18a |
| Security info panel | Prominent "How we protect your keys" — reuse `KeyProtectionInfo.vue` |
| "At least one key" validation | "Create Workspace" disabled until ≥1 provider configured |
| Backend: keyless workspace creation | `POST /api/workspace/init` no longer requires `api_key` body field |
| Migration: old onboarding | Remove single Anthropic-only key input |

**What this step does NOT cover**:
- Model selection (step 18c)
- LiteLLM backend (step 18b)

---

## File Structure

```
frontend/
  app/
    pages/
      onboarding.vue              # REWRITE — multi-provider welcome flow
    components/
      ProviderCard.vue            # REUSE from 18a (no changes)
      AddKeyModal.vue             # REUSE from 18a (no changes)
      KeyProtectionInfo.vue       # REUSE from 18a (no changes)
backend/
  routers/
    workspace.py                  # MODIFY — api_key optional in init
  services/
    workspace_service.py          # MODIFY — create_workspace without mandatory key
  tests/
    test_workspace_api.py         # MODIFY — test keyless init
    test_onboarding_flow.py       # NEW — E2E onboarding tests
```

---

## UX Flow

### Screen 1 — Welcome + Key Setup (single page, no multi-step wizard)

```
┌──────────────────────────────────────────────────────┐
│                                                       │
│                      ✦ JARVIS                         │
│           Personal Memory & Planning System           │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 🔒  Your keys stay in your browser               │ │
│  │                                                   │ │
│  │  • Stored locally — never sent to our server     │ │
│  │  • Passed directly to the AI provider's API      │ │
│  │  • Session keys clear when you close the tab     │ │
│  │  • You can add or remove keys anytime in Settings│ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  Add at least one AI provider to get started:         │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 🤖  Anthropic                        [Add Key]   │ │
│  │     Claude Sonnet, Haiku                          │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ ✨  OpenAI                           [Add Key]   │ │
│  │     GPT-4o, o3-mini                               │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ G   Google AI                        [Add Key]   │ │
│  │     Gemini 2.5 Flash, Pro                         │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│           [ Create Jarvis Workspace ]                 │
│           (disabled until ≥1 key added)               │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 💡 Don't have a key yet?                         │ │
│  │    Get one free at console.anthropic.com →        │ │
│  │    or platform.openai.com →                       │ │
│  │    or aistudio.google.com →                       │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### After Adding a Key — Card Updates

```
┌──────────────────────────────────────────────────────┐
│  🤖  Anthropic              ✅ Configured   [Remove] │
│      sk-ant-****            this session only         │
├──────────────────────────────────────────────────────┤
│  ✨  OpenAI                              [Add Key]   │
│      GPT-4o, o3-mini                                  │
├──────────────────────────────────────────────────────┤
│  G   Google AI                           [Add Key]   │
│      Gemini 2.5 Flash, Pro                            │
└──────────────────────────────────────────────────────┘

         [ Create Jarvis Workspace ]    ← NOW ENABLED
```

### After Clicking "Create Workspace"

1. Button shows spinner: "Creating..."
2. `POST /api/workspace/init` — **no api_key in body** (keys are in browser)
3. Backend creates folder structure + SQLite + config.json
4. On success → redirect to `/main`
5. `useApiKeys().activeProvider` auto-set to first configured provider

---

## Backend Changes

### `POST /api/workspace/init` — Updated

**Before (current):**
```json
{
  "api_key": "sk-ant-...",
  "workspace_path": "~/Jarvis"
}
```

**After:**
```json
{
  "workspace_path": "~/Jarvis"
}
```

- `api_key` becomes **optional** (for backward compat, if provided → still store in keyring as Anthropic fallback)
- Workspace creation succeeds without any key
- `config.json` gets `"api_key_set": false` (or `true` if legacy key provided)
- New `config.json` field: `"key_storage": "browser"` — indicates keys are browser-managed

### workspace_service.py

```python
def create_workspace(
    api_key: str | None = None,  # NOW OPTIONAL
    workspace_path: Path | None = None,
) -> dict:
    path = workspace_path or get_settings().workspace_path
    # Create folder structure (unchanged)
    _create_folder_tree(path)
    # Create SQLite DB (unchanged)
    _init_database(path)
    # Config
    config = {
        "created_at": datetime.now().isoformat(),
        "api_key_set": bool(api_key),
        "key_storage": "browser" if not api_key else "server",
    }
    # Legacy: if key provided, store in keyring
    if api_key:
        _store_api_key(api_key, path)
    # Write config
    (path / "app" / "config.json").write_text(json.dumps(config, indent=2))
    return {"status": "ok", "workspace_path": str(path)}
```

---

## Provider Card Enhancements for Onboarding

The `ProviderCard.vue` from step 18a needs a small extension for onboarding context:

```typescript
props: {
  provider: ProviderConfig,
  showModels: boolean  // NEW — show available models below name (onboarding only)
}
```

When `showModels` is true, the card shows model names below the provider name:

```
🤖  Anthropic                        [Add Key]
    Claude Sonnet, Haiku
```

This helps first-time users understand what each provider offers.

---

## Validation Rules

| Rule | Behavior |
|------|---------|
| No keys added | "Create Workspace" disabled, tooltip: "Add at least one AI provider key" |
| ≥1 key added | "Create Workspace" enabled |
| Key added then removed (back to 0) | Button disabled again |
| Backend offline | Show error: "Cannot reach backend. Is it running?" (existing behavior) |
| Workspace already exists | Redirect to `/main` (existing guard in `index.vue`) |

---

## What Happens to the Current Onboarding

The current `onboarding.vue` is a simple form with one input (`sk-ant-...`) + "Create Jarvis Workspace" button. It gets **fully replaced** by the new multi-provider layout.

### Backward Compatibility

- If user already has a workspace with a keyring-stored Anthropic key → they never see onboarding again (existing guard works)
- If user goes to Settings → they see the same provider cards (from step 18a) and can add/remove keys
- If user clears browser storage → they still have the server-stored key as fallback
- New users (post-18d) → keys only in browser, no server storage

---

## Security Info — Copy

The `KeyProtectionInfo.vue` box from step 18a is reused here, but with a slightly different intro for the onboarding context:

**Onboarding version:**
> 🔒 **Your keys stay in your browser**
>
> - Stored locally — never sent to our server
> - Passed directly to the AI provider's API
> - Session keys clear when you close the tab
> - You can add or remove keys anytime in Settings

**Settings version** (from 18a):
> ℹ️ **How we protect your keys**
>
> - Keys are stored in your browser only
> - Never sent to our server or logged
> - Passed directly to the AI provider
> - Session keys clear when you close tab

Same component, different `title` and `icon` props:
```typescript
props: {
  title: string    // "Your keys stay in your browser" | "How we protect your keys"
  icon: string     // "🔒" | "ℹ️"
}
```

---

## "Don't Have a Key?" Helper

Bottom section with direct links to each provider's key page:

```typescript
const KEY_HELP_LINKS = PROVIDERS.map(p => ({
  name: p.name,
  url: p.docsUrl,
  icon: p.icon,
}))
```

Renders as a subtle info box:
```
💡 Don't have a key yet?
   Get one free at console.anthropic.com →
   or platform.openai.com →
   or aistudio.google.com →
```

Links open in new tab (`target="_blank" rel="noopener"`).

---

## Acceptance Criteria

1. First-time user sees new onboarding with all 3 provider cards
2. "Create Workspace" disabled until ≥1 key added
3. Adding key via modal → card shows ✅ Configured → button enables
4. Removing all keys → button disables again
5. "Create Workspace" creates workspace **without sending key to backend**
6. After creation → redirect to `/main`
7. Security info box is prominently visible
8. "Don't have a key?" links open provider console pages
9. `POST /api/workspace/init` works without `api_key` in body
10. Legacy flow (with `api_key`) still works for backward compat
11. Existing users (workspace exists) still skip onboarding

---

## Tests

### Frontend (Vitest)
- Onboarding renders 3 provider cards
- Button disabled when no keys, enabled when ≥1 key
- AddKeyModal opens on "Add Key" click
- Workspace creation calls API without `api_key`
- Redirect to `/main` on success

### Backend (pytest)
- `POST /api/workspace/init` without `api_key` → 200 + workspace created
- `POST /api/workspace/init` with `api_key` → 200 + key stored (backward compat)
- Workspace status returns correctly for keyless workspace

---

## Design Notes

- Keep the same dark theme (`#111122` background, `#222` borders) as current onboarding
- Provider cards use same styling as Settings page (visual consistency)
- "Create Workspace" button uses existing `#6ab0f3` accent color
- No animations beyond what `AddKeyModal` already has from step 18a
- Mobile-responsive: cards stack vertically on narrow screens
