# Step 21b — Local Models: Settings UI

> **Goal**: Add "Local Models" section to the Settings page with Ollama
> runtime status, hardware-aware model recommendations, download with
> progress bar, and model activation. Integrate local models into the
> existing ModelSelector dropdown.

**Status**: ⬜ Not started
**Depends on**: Step 21a (backend endpoints)
**Effort**: ~2–3 days
**Branch**: `feat/local-models-frontend`

---

## Why This Matters

Users need a clear, guided way to discover, download, and activate local
models from within Jarvis — without leaving the app or touching the terminal.
The Settings page already has "AI Providers" for cloud keys. This step adds
a parallel "Local Models" section below it with hardware-aware recommendations.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `useLocalModels.ts` composable | Fetch hardware, runtime, catalog, manage pull state |
| `OllamaStatus.vue` | Runtime status card (installed / running / not found) |
| `LocalModelCard.vue` | Model card with specs, compatibility badge, download button |
| Settings page extension | New "Run locally" section below cloud providers |
| `ModelSelector.vue` changes | Show local models alongside cloud models |
| Pull progress | SSE-based progress bar during model download |
| Provider integration | `useApiKeys.ts` extended with `ollama` provider (no key needed) |

**What this step does NOT cover**:
- Onboarding flow changes (step 21c)
- Tool calling badge / degradation (step 21d)

---

## File Structure

```
frontend/
  app/
    composables/
      useLocalModels.ts            # NEW — local model state & API calls
    components/
      OllamaStatus.vue             # NEW — runtime status card
      LocalModelCard.vue           # NEW — model recommendation card
      PullProgress.vue             # NEW — download progress bar
    pages/
      settings.vue                 # MODIFY — add Local Models section
    components/
      ModelSelector.vue            # MODIFY — include local models
    composables/
      useApiKeys.ts                # MODIFY — add ollama provider (keyless)
      providerIcons.ts             # MODIFY — add ollama icon
    types/
      index.ts                     # MODIFY — add local model types
  tests/
    useLocalModels.test.ts         # NEW — composable unit tests
```

---

## Types

Add to `frontend/app/types/index.ts`:

```typescript
/* ---- Local Models ---- */

export type HardwareTier = 'light' | 'balanced' | 'strong' | 'workstation'
export type ModelCompatibility = 'great' | 'good' | 'warning' | 'unsupported'
export type LocalModelPreset = 'fast' | 'everyday' | 'balanced' | 'long-docs'
  | 'reasoning' | 'code' | 'best-local'

export interface HardwareProfile {
  os: string
  arch: string
  total_ram_gb: number
  free_disk_gb: number
  cpu_cores: number
  gpu_vendor?: string
  gpu_vram_gb?: number
  is_apple_silicon: boolean
  tier: HardwareTier
}

export interface RuntimeStatus {
  runtime: string
  installed: boolean
  running: boolean
  base_url: string
  version?: string
  reachable: boolean
}

export interface ModelRecommendation {
  model_id: string
  preset: LocalModelPreset
  label: string
  download_size_gb: number
  context_window: string
  strengths: string[]
  best_for: string[]
  recommended_ram: string
  native_tools: boolean
  compatibility: ModelCompatibility
  score: number
  recommended: boolean
  reason: string
  installed: boolean
  active: boolean
}

export interface PullProgress {
  status: string
  digest?: string
  total?: number
  completed?: number
}
```

---

## `useLocalModels.ts` Composable

### State

```typescript
const hardware = useState<HardwareProfile | null>('local-hardware', () => null)
const runtime = useState<RuntimeStatus | null>('local-runtime', () => null)
const catalog = useState<ModelRecommendation[]>('local-catalog', () => [])
const pulling = useState<string | null>('local-pulling', () => null)        // model_id being pulled
const pullProgress = useState<PullProgress | null>('local-pull-progress', () => null)
const loading = useState<boolean>('local-loading', () => false)
const error = useState<string | null>('local-error', () => null)
```

### Methods

```typescript
async function fetchHardware(): Promise<void>
async function fetchRuntime(): Promise<void>
async function fetchCatalog(): Promise<void>
async function refreshAll(): Promise<void>         // hardware + runtime + catalog
async function pullModel(modelId: string): Promise<void>   // SSE stream
async function selectModel(modelId: string): Promise<void>
function isOllamaReady(): boolean                  // installed && running
```

### SSE Pull Implementation

```typescript
async function pullModel(modelId: string): Promise<void> {
  const model = catalog.value.find(m => m.model_id === modelId)
  if (!model) return

  pulling.value = modelId
  pullProgress.value = { status: 'starting' }

  const response = await fetch('/api/local/models/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: model.ollama_model,    // e.g. "qwen3:8b"
      base_url: runtime.value?.base_url ?? 'http://localhost:11434',
    }),
  })

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value)
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        pullProgress.value = data
        if (data.status === 'done' || data.status === 'success') {
          pulling.value = null
          await fetchCatalog()      // refresh installed status
        }
      }
    }
  }
}
```

---

## `OllamaStatus.vue`

Runtime status card at the top of the Local Models section.

### States

**Not Installed**:
```
┌──────────────────────────────────────────────┐
│  🔴  Ollama not found                        │
│                                              │
│  Ollama is required to run local AI models.  │
│                                              │
│  [ Install Ollama ↗ ]   [ Check Again ]      │
└──────────────────────────────────────────────┘
```
"Install Ollama" opens `https://ollama.com/download` in new tab.

**Installed but Not Running**:
```
┌──────────────────────────────────────────────┐
│  🟡  Ollama installed but not running        │
│                                              │
│  Start Ollama to use local models.           │
│  Run: ollama serve                           │
│                                              │
│  [ Check Again ]                             │
└──────────────────────────────────────────────┘
```

**Running**:
```
┌──────────────────────────────────────────────┐
│  🟢  Ollama running   v0.9.x                │
│      localhost:11434                         │
│                                              │
│  Your computer: 32 GB RAM · Apple Silicon    │
│  Hardware class: Strong                      │
└──────────────────────────────────────────────┘
```

---

## `LocalModelCard.vue`

One card per model in the catalog.

### Props

```typescript
interface Props {
  model: ModelRecommendation
  pulling: boolean              // this model is currently downloading
  progress: PullProgress | null
}
```

### Layout

```
┌──────────────────────────────────────────────┐
│  Qwen3 8B                        [Balanced]  │
│                                              │
│  Best on 16–32 GB RAM                        │
│  Download 5.2 GB · Context 40K               │
│                                              │
│  💬 chat  🌍 multilingual  🔧 tools          │
│                                              │
│  ✅ Recommended — fits your 32 GB RAM        │
│                                              │
│  [ Download & Use ]                          │
└──────────────────────────────────────────────┘
```

### Compatibility Badges

| Compatibility | Color | Label |
|---------------|-------|-------|
| `great` | green | ✅ Recommended |
| `good` | blue | 👍 Compatible |
| `warning` | amber | ⚠️ May be slow |
| `unsupported` | red/gray | ❌ Not enough resources |

### Button States

| State | Button |
|-------|--------|
| Not installed, compatible | `Download & Use` (primary) |
| Not installed, warning | `Download & Use` (secondary, with warning) |
| Not installed, unsupported | `Download` (disabled) |
| Pulling this model | Progress bar + percentage |
| Installed, not active | `Use This Model` |
| Installed, active | `Active ✓` (disabled) |

---

## `PullProgress.vue`

Shown during model download, replaces the action button.

```
┌──────────────────────────────────────────────┐
│  Downloading qwen3:8b...                     │
│  ████████████░░░░░░░░ 58%                    │
│  3.0 GB / 5.2 GB                             │
│                                              │
│  Pulling layers...                           │
└──────────────────────────────────────────────┘
```

Progress percentage: `Math.round((completed / total) * 100)`.
Show human-readable sizes: `(completed / 1e9).toFixed(1) GB`.

---

## Settings Page Changes

### Current Structure (simplified)

```
Settings
├── AI Providers (cloud)
│   ├── Anthropic card
│   ├── OpenAI card
│   └── Google AI card
├── Voice
└── Budget
```

### New Structure

```
Settings
├── AI Providers (cloud)
│   ├── Anthropic card
│   ├── OpenAI card
│   └── Google AI card
├── Local Models              ← NEW SECTION
│   ├── OllamaStatus
│   ├── Recommended Models (top 3, if runtime ready)
│   ├── All Models (expandable, if runtime ready)
│   └── Ollama Base URL setting
├── Voice
└── Budget
```

### Section Header

```
── Local Models ──────────────────────────────

Run Jarvis locally
Private on-device AI. Models are downloaded to your computer.
No API key needed.
```

### Recommended vs All

- **Recommended**: Show top 3 models (where `recommended === true`)
- **All Models**: Expandable section with all 7 presets
- Filter pills: `All · General · Docs · Code · Reasoning`

---

## ModelSelector Integration

### Current Behavior

`ModelSelector.vue` shows a dropdown grouped by provider:
```
Anthropic
  Claude Sonnet 4        $$
  Claude Haiku 4.5       $
  Claude Opus 4          $$$
OpenAI
  GPT-4o                 $$
  ...
```

### New Behavior

Add "Local" group at the bottom (only if any local model is installed):

```
Anthropic
  Claude Sonnet 4        $$
  ...
OpenAI
  GPT-4o                 $$
  ...
─── Local ───
  Qwen3 8B               🖥️
  Qwen3 4B               🖥️
```

When user selects a local model:
- `activeProvider` → `"ollama"`
- `activeModel` → `"ollama_chat/qwen3:8b"`
- No API key sent in WebSocket payload

---

## `useApiKeys.ts` Changes

### Add Ollama as Provider (Keyless)

```typescript
// Add to PROVIDERS array:
{
  id: 'ollama',
  name: 'Local (Ollama)',
  icon: PROVIDER_ICONS.ollama,
  keyPrefix: '',                 // no key
  docsUrl: 'https://ollama.com',
  models: [],                    // populated dynamically from useLocalModels
  color: '#FFFFFF',
}
```

### Skip Key Requirement for Ollama

```typescript
function isConfigured(providerId: string): boolean {
  if (providerId === 'ollama') {
    // Ollama is "configured" if runtime is reachable + model installed
    return true  // actual check delegated to useLocalModels
  }
  return !!getKey(providerId)
}
```

### Active Provider Logic

When `activeProvider === 'ollama'`:
- `activeKey` returns `undefined` (no key needed)
- `sendMessage()` omits `api_key` from payload
- Chat composable sends `provider: "ollama"` + `model: "ollama_chat/..."` 

---

## `providerIcons.ts` Changes

Add Ollama icon (simple SVG — llama silhouette or generic local icon):

```typescript
export const PROVIDER_ICONS = {
  // ... existing
  ollama: '<svg>...</svg>',  // local/computer icon
}
```

---

## Ollama Base URL Setting

Small text input in the Local Models section:

```
Ollama URL: [http://localhost:11434    ]  [Test Connection]
```

Default: `http://localhost:11434`
Stored in localStorage: `jarvis-ollama-base-url`
Passed to all backend calls as `base_url` parameter.

---

## Risks & Mitigations (Frontend-specific)

| Risk | Impact | Mitigation |
|------|--------|------------|
| SSE connection drops during large download | User thinks download failed | Auto-retry with resume; show "Retrying..." message |
| User closes tab during pull | Download continues in Ollama but UI loses state | On next load, check `/api/tags` to see if model appeared |
| Runtime goes away between catalog fetch and pull | Pull fails | Re-probe runtime before pull; clear error if unreachable |
| Many models installed → cluttered ModelSelector | Hard to find the right model | Group under "Local" header; show only installed models in selector |
| No Ollama installed + no cloud key | User stuck | Onboarding handles this (step 21c) — show both paths clearly |

---

## Tests

```typescript
// useLocalModels.test.ts

describe('useLocalModels', () => {
  it('fetches hardware profile')
  it('fetches runtime status')
  it('fetches catalog with recommendations')
  it('identifies recommended models')
  it('handles runtime not reachable')
  it('pull model updates progress reactively')
  it('select model updates active state')
})
```

---

## Definition of Done

- [ ] `useLocalModels.ts` composable with hardware/runtime/catalog/pull/select
- [ ] `OllamaStatus.vue` shows 3 states (not installed / not running / running)
- [ ] `LocalModelCard.vue` with compatibility badge + download button
- [ ] `PullProgress.vue` with percentage bar
- [ ] Settings page has "Local Models" section
- [ ] `ModelSelector.vue` shows installed local models under "Local" group
- [ ] `useApiKeys.ts` handles `ollama` provider without key
- [ ] Ollama base URL configurable
- [ ] SSE pull streaming works end-to-end
- [ ] Provider icon added for Ollama
- [ ] Types added to `types/index.ts`
