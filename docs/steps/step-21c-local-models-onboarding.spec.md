# Step 21c — Local Models: Onboarding + Settings Welcome Flow

> **Goal**: Extend both the **Onboarding page** (first-time users) and the
> **Settings page** (returning users) to offer a clear choice between
> cloud AI and local AI. Users who don't have an API key can still
> start Jarvis with a local model.

**Status**: ⬜ Not started
**Depends on**: Step 21b (frontend components exist)
**Effort**: ~1–2 days
**Branch**: `feat/local-models-onboarding`

---

## Why This Matters

Currently, onboarding **requires at least one cloud API key**. The "Create
Workspace" button is disabled until a key is added. With local models,
users should be able to start Jarvis with **zero API keys** — just Ollama
and a downloaded model. Both entry points (onboarding and settings) must
present this path clearly.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Onboarding redesign | Two-path choice: Cloud AI vs Local AI |
| Keyless workspace creation | Allow "Create Workspace" with local model, no cloud key |
| Local model onboarding flow | Detect hardware → detect Ollama → recommend → download → activate |
| Settings: local quick-start | Banner in Settings for users who haven't tried local models |
| Validation logic change | `canCreate` = has cloud key OR has active local model |

**What this step does NOT cover**:
- Backend endpoints (step 21a — already done)
- Component internals (step 21b — already done)
- Tool calling degradation (step 21d)

---

## File Structure

```
frontend/
  app/
    pages/
      onboarding.vue               # MODIFY — add local AI path
    pages/
      settings.vue                 # MODIFY — add "Try local AI" banner
    components/
      OnboardingLocalFlow.vue      # NEW — local model setup wizard in onboarding
    composables/
      useApiKeys.ts                # MODIFY — canCreate logic
```

---

## Onboarding Page Redesign

### Current Flow (step 18d)

```
┌──────────────────────────────────────────┐
│              ✦ JARVIS                     │
│   Personal Memory & Planning System      │
│                                          │
│   🔒 Your keys stay in your browser      │
│                                          │
│   Add at least one AI provider:          │
│   ┌─ Anthropic ──────── [Add Key] ─┐    │
│   ├─ OpenAI ────────── [Add Key] ──┤    │
│   └─ Google AI ─────── [Add Key] ──┘    │
│                                          │
│   [ Create Jarvis Workspace ]            │
│   (disabled until ≥1 key added)          │
└──────────────────────────────────────────┘
```

### New Flow

**Phase 1 — Choose Your AI**

```
┌──────────────────────────────────────────────────────┐
│                     ✦ JARVIS                          │
│          Personal Memory & Planning System            │
│                                                       │
│   How would you like to power Jarvis?                 │
│                                                       │
│   ┌────────────────────┐  ┌─────────────────────────┐ │
│   │  ☁️  Use Cloud AI   │  │  🖥️  Run Locally        │ │
│   │                    │  │                         │ │
│   │  Anthropic, OpenAI │  │  Private, on-device AI  │ │
│   │  Google AI         │  │  No API key needed      │ │
│   │                    │  │  Powered by Ollama      │ │
│   │  Needs API key     │  │  Free & offline         │ │
│   │                    │  │                         │ │
│   │  [ Choose Cloud ]  │  │  [ Choose Local ]       │ │
│   └────────────────────┘  └─────────────────────────┘ │
│                                                       │
│   💡 You can use both! Add cloud keys and local       │
│      models anytime in Settings.                      │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**Phase 2a — Cloud Path** (existing flow, unchanged)

User clicked "Choose Cloud" → shows the current provider cards + key entry.
"Create Workspace" enabled when ≥1 key is added.

**Phase 2b — Local Path** (new)

User clicked "Choose Local" → shows `OnboardingLocalFlow.vue`:

```
┌──────────────────────────────────────────────────────┐
│                   🖥️ Local AI Setup                   │
│                                                       │
│   ┌─────────────────────────────────────────────┐     │
│   │ Your Computer                               │     │
│   │ macOS · Apple Silicon · 32 GB RAM           │     │
│   │ Hardware class: Strong                      │     │
│   └─────────────────────────────────────────────┘     │
│                                                       │
│   ┌─────────────────────────────────────────────┐     │
│   │ 🟢 Ollama running  v0.9.x                  │     │
│   │    localhost:11434                           │     │
│   └─────────────────────────────────────────────┘     │
│                                                       │
│   Recommended for your computer:                      │
│                                                       │
│   ┌─────────────────────────────────────────────┐     │
│   │ ⭐ Qwen3 8B                     Balanced    │     │
│   │ Best on 16–32 GB · 5.2 GB · 40K context    │     │
│   │ ✅ Recommended — fits your 32 GB RAM        │     │
│   │ [ Download & Start Using Jarvis ]            │     │
│   └─────────────────────────────────────────────┘     │
│                                                       │
│   ┌─ Qwen3 4B ── Everyday ── 2.5 GB ── [Use] ──┐    │
│   └─ Ministral 3 ── Long Docs ── 6 GB ── [Use] ─┘   │
│                                                       │
│   [ ← Back to choices ]      [ Show all models ]     │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### Ollama Not Found (in Local Path)

```
┌──────────────────────────────────────────────────────┐
│                   🖥️ Local AI Setup                   │
│                                                       │
│   ┌─────────────────────────────────────────────┐     │
│   │ 🔴 Ollama not found on your system          │     │
│   │                                             │     │
│   │ Ollama is a free tool that runs AI models   │     │
│   │ on your computer. Install it first:         │     │
│   │                                             │     │
│   │ [ Download Ollama ↗ ]                       │     │
│   │                                             │     │
│   │ After installing, click Check Again.        │     │
│   │                                             │     │
│   │ [ Check Again ]                             │     │
│   └─────────────────────────────────────────────┘     │
│                                                       │
│   [ ← Back to choices ]                              │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### Download Progress (in Local Path)

```
┌──────────────────────────────────────────────────────┐
│                   🖥️ Setting up Jarvis                │
│                                                       │
│   Downloading Qwen3 8B...                             │
│   ████████████████░░░░░░░░ 67%                        │
│   3.5 GB / 5.2 GB                                     │
│                                                       │
│   Pulling layers...                                   │
│                                                       │
│   This may take a few minutes depending on your       │
│   internet connection.                                │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### After Download → Workspace Creation

```
┌──────────────────────────────────────────────────────┐
│                   ✅ Ready to go!                     │
│                                                       │
│   Qwen3 8B is ready on your computer.                │
│                                                       │
│   [ Create Jarvis Workspace ]                         │
│                                                       │
│   💡 You can also add cloud AI keys later in Settings │
│                                                       │
└──────────────────────────────────────────────────────┘
```

---

## `OnboardingLocalFlow.vue`

### Component Responsibilities

1. Call `useLocalModels().refreshAll()` on mount
2. Show hardware profile
3. Show Ollama status (reuse `OllamaStatus.vue`)
4. Show top 3 recommended models (reuse `LocalModelCard.vue`)
5. Handle "Download & Start" flow (pull → select → enable workspace button)
6. Emit `@model-ready` when a model is installed + selected

### Props & Events

```typescript
interface Props {
  // none — uses composables
}

interface Emits {
  (e: 'model-ready'): void
  (e: 'back'): void
}
```

---

## Onboarding Page State Machine

```
┌──────────┐
│  choose   │ ← initial state
│  cloud/   │
│  local    │
└─────┬─────┘
      │
  ┌───┴───┐
  │       │
  ▼       ▼
┌─────┐ ┌─────┐
│cloud│ │local│
│keys │ │setup│
└──┬──┘ └──┬──┘
   │       │
   │  ┌────┴─────┐
   │  │ pulling  │ (download in progress)
   │  └────┬─────┘
   │       │
   ▼       ▼
┌──────────────┐
│  can_create  │ ← ≥1 cloud key OR local model ready
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  creating    │ ← workspace init
└──────────────┘
```

### State Variable

```typescript
type OnboardingPhase = 'choose' | 'cloud' | 'local' | 'ready'
const phase = ref<OnboardingPhase>('choose')
```

---

## `canCreate` Logic Change

### Current (in `onboarding.vue`)

```typescript
const canCreate = computed(() => apiKeys.configuredCount() > 0)
```

### New

```typescript
const localModels = useLocalModels()

const canCreate = computed(() => {
  const hasCloudKey = apiKeys.configuredCount() > 0
  const hasLocalModel = localModels.catalog.value.some(m => m.installed && m.active)
  return hasCloudKey || hasLocalModel
})
```

---

## Settings Page: "Try Local AI" Banner

For returning users who only have cloud keys and haven't tried local models.

Show a subtle banner at the top of the Local Models section:

```
┌──────────────────────────────────────────────────────┐
│  🖥️  Run Jarvis locally — free & private             │
│  Download a model to use Jarvis without an API key.  │
│  [ Set up local AI ]                                 │
└──────────────────────────────────────────────────────┘
```

This banner hides once any local model is installed.

Both the Settings page and the Onboarding page use the same underlying
components (`OllamaStatus`, `LocalModelCard`, `PullProgress`) — just
with different layout and messaging.

---

## Backend: Keyless Workspace Creation

### Current Behavior

`POST /api/workspace/init` already works without `api_key` (step 18d made it
optional). No backend change needed for workspace creation.

### New Config Field

When workspace is created via local path, save local model selection:

```json
{
  "local_model": {
    "active": true,
    "model_id": "qwen3-8b",
    "litellm_model": "ollama_chat/qwen3:8b",
    "base_url": "http://localhost:11434"
  }
}
```

This is already handled by `POST /api/local/models/select` from step 21a.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| User picks "Local" but has no Ollama | Dead end | Clear install instructions + link + "Check Again" button |
| User installs Ollama but doesn't start it | Can't reach Ollama API | Show "Run `ollama serve`" instruction + "Check Again" |
| Download takes very long on slow internet | User abandons onboarding | Show estimated time; allow switching to Cloud path mid-download |
| User has both cloud key AND local model | Confusing which is active | Clear indicator in ModelSelector; last selected wins |
| Ollama service stops after reboot | Models stop working next session | Runtime probe on app start; banner "Ollama not running" in main view |
| User picks local on underpowered machine | Very slow responses | Show "warning" compatibility; add "Local models are slower than cloud" hint |

---

## Tests

```typescript
// onboarding-local.test.ts

describe('Onboarding local flow', () => {
  it('shows choose screen by default')
  it('clicking "Choose Local" shows local setup')
  it('clicking "Choose Cloud" shows provider cards')
  it('back button returns to choose screen')
  it('canCreate is true when local model active')
  it('canCreate is true when cloud key added')
  it('canCreate is false when neither')
  it('shows Ollama install prompt when not found')
  it('shows recommended models when Ollama running')
  it('download triggers pull and shows progress')
  it('after download, shows Create Workspace button')
})
```

---

## Definition of Done

- [ ] Onboarding shows "Cloud vs Local" choice screen
- [ ] Cloud path works exactly as before
- [ ] Local path: hardware → Ollama check → recommend → download → ready
- [ ] `OnboardingLocalFlow.vue` reuses step 21b components
- [ ] `canCreate` accepts local model as valid (no cloud key needed)
- [ ] Settings page has "Try local AI" banner for cloud-only users
- [ ] "Back" navigation works between phases
- [ ] Ollama-not-found state shows install instructions
- [ ] Download progress visible during onboarding
- [ ] Workspace created successfully with only local model
