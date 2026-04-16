# Step 21d — Local Models: Integration, Tool Calling & Resilience

> **Goal**: Handle edge cases that arise when local models are actually used
> for chat: tool calling degradation, timeout tuning, reconnection logic,
> and runtime health monitoring. Make local models a first-class citizen
> in the chat pipeline.

**Status**: ✅ Complete
**Depends on**: Step 21a (backend), Step 21b (frontend), Step 21c (onboarding)
**Effort**: ~1–2 days
**Branch**: `feat/local-models-integration`

---

## Why This Matters

Local models have fundamentally different characteristics than cloud APIs:
- **Speed**: 2–30 tok/s on CPU vs 50–100+ tok/s cloud
- **Tool support**: Not all models support native function calling
- **Reliability**: Runtime can stop, restart, or crash
- **Timeouts**: Default timeouts designed for cloud APIs are too aggressive

Without handling these, users will see broken experiences: frozen UIs,
missing tool results, silent failures.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| Tool calling mode detection | Detect if model supports native tools or needs JSON fallback |
| Tool badge in UI | Show "Native tools" or "Tools via prompt" badge on model cards |
| Timeout configuration | Per-provider timeout overrides (longer for local) |
| Runtime health check | Periodic probe on chat page; banner if Ollama goes down |
| Reconnection flow | Clear error + "Reconnect" button when Ollama unreachable |
| Slow response indicator | Visual cue when local model is generating slowly |
| Model warm-up | Optional pre-load / keep-alive after model selection |

**What this step does NOT cover**:
- Adding more runtimes (vLLM, llama.cpp) — future work
- Auto-starting Ollama — OS-level, out of scope
- Mobile/tablet support — out of scope

---

## File Structure

```
backend/
  services/
    ollama_service.py              # MODIFY — add tool support detection, warm-up
    llm_service.py                 # MODIFY — timeout overrides, api_base forwarding
  routers/
    local_models.py                # MODIFY — add test endpoint, warm-up endpoint
    chat.py                        # MODIFY — timeout per provider
  tests/
    test_local_models_integration.py  # NEW
frontend/
  app/
    composables/
      useLocalModels.ts            # MODIFY — health polling, warm-up
    components/
      LocalModelCard.vue           # MODIFY — tool badge
      OllamaStatus.vue             # MODIFY — reconnect button
      StatusBar.vue                # MODIFY — local model status indicator
    pages/
      main.vue                    # MODIFY — runtime health polling
```

---

## 1. Tool Calling Mode Detection

### Problem

LiteLLM supports Ollama tool calling, but **not all Ollama models implement
native function calling**. When a model doesn't support it, LiteLLM falls back
to JSON-mode tool calls (injecting tool schemas into the system prompt).
This works but is less reliable.

### Model Catalog Extension

Add `native_tools` field to each model in the catalog:

| Model | Native Tools | Notes |
|-------|-------------|-------|
| `qwen3:1.7b` | ❌ | Too small for reliable tool use |
| `qwen3:4b` | ⚠️ | JSON fallback, works for simple tools |
| `qwen3:8b` | ✅ | Qwen3 has tool calling support |
| `ministral-3:8b` | ⚠️ | JSON fallback |
| `gemma4:e4b` | ✅ | Gemma4 supports tool calling |
| `devstral-small-2:24b` | ✅ | Designed for agentic use |
| `gemma4:26b` | ✅ | Full tool support |

### Backend: Tool Mode in Catalog Response

```python
class ModelRecommendation(BaseModel):
    # ... existing fields
    native_tools: bool
    tool_mode: str  # "native" | "json_fallback" | "limited"
```

### Frontend: Tool Badge on Model Card

Show small badge below model strengths:

- ✅ **Native tools** — green badge
- ⚠️ **Tools via prompt** — amber badge
- ❌ **Limited tool support** — gray badge, tooltip: "This model may not
  reliably use Jarvis tools like search, write, plan"

### LLMService: Handling Fallback

LiteLLM handles JSON fallback automatically. No code change needed in
`LLMService` — but add a note in the response metadata:

```python
# In StreamEvent or done event:
{
    "type": "done",
    "model": "ollama_chat/qwen3:4b",
    "provider": "ollama",
    "tool_mode": "json_fallback"  # NEW
}
```

Frontend can display a subtle hint: "This model uses simplified tool handling"
if tool_mode != "native".

---

## 2. Timeout Configuration

### Problem

Default LiteLLM timeout is ~10 minutes. Local models on CPU can take 30–60s
just for first token (model loading). But cloud APIs respond in <2s.

### Solution

Per-provider timeout in `LLMConfig`:

```python
@dataclass
class LLMConfig:
    # ... existing
    timeout: Optional[float] = None  # seconds; None = provider default

PROVIDER_TIMEOUTS = {
    "anthropic": 120,    # 2 min
    "openai": 120,
    "google": 120,
    "ollama": 600,       # 10 min — local models are slow
}
```

Pass to LiteLLM:
```python
response = await acompletion(
    model=self.config.model,
    messages=messages,
    timeout=self.config.timeout or PROVIDER_TIMEOUTS.get(self.config.provider, 120),
    # ...
)
```

### Frontend: Slow Response Indicator

If no tokens received after 10s for local model, show:

```
⏳ Local model is loading... This may take a moment.
```

After 30s with no response:

```
⏳ Still generating... Local models can be slow on CPU.
   Consider a smaller model if this is too slow.
```

This is a simple timer in the chat composable, not a new component.

---

## 3. Runtime Health Monitoring

### Problem

User starts Jarvis, Ollama is running. User goes to lunch, comes back,
Ollama has stopped (crash, sleep, restart). Chat silently fails.

### Solution: Periodic Health Poll

In `useLocalModels.ts`, add a polling mechanism:

```typescript
let healthInterval: ReturnType<typeof setInterval> | null = null

function startHealthPolling(intervalMs = 30_000): void {
  stopHealthPolling()
  healthInterval = setInterval(async () => {
    if (activeProvider.value !== 'ollama') return
    await fetchRuntime()
    if (!runtime.value?.reachable) {
      // Emit event or set state for UI to react
      ollamaDown.value = true
    } else {
      ollamaDown.value = false
    }
  }, intervalMs)
}
```

### UI: Banner When Ollama Goes Down

Show a non-blocking banner at the top of the chat panel:

```
┌──────────────────────────────────────────────┐
│  ⚠️  Ollama is not responding                │
│  Local model chat is unavailable.            │
│  [ Reconnect ]  [ Switch to Cloud AI ]       │
└──────────────────────────────────────────────┘
```

"Reconnect" calls `fetchRuntime()` again.
"Switch to Cloud AI" opens model selector.

Only shown when `activeProvider === 'ollama'` and `ollamaDown === true`.

### StatusBar Integration

`StatusBar.vue` currently shows WebSocket connection state.
Add local model indicator:

```
Connected · Qwen3 8B (local) · 🟢
Connected · Qwen3 8B (local) · 🔴 Ollama offline
```

---

## 4. Model Warm-up / Keep-Alive

### Problem

Ollama unloads models from memory after idle timeout (default: 5 min).
First request after idle is slow because model needs to reload.

### Solution

Add optional warm-up endpoint:

```python
# POST /api/local/models/warm-up
async def warm_up_model(req: WarmUpRequest):
    """Send a tiny prompt to keep model loaded."""
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{req.base_url}/api/chat",
            json={
                "model": req.model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "keep_alive": "30m",  # Ollama keep_alive parameter
            },
        )
    return {"status": "warm"}
```

Frontend: after selecting a local model, optionally call warm-up.
Not blocking — fire-and-forget in background.

---

## 5. Test Endpoint

### `POST /api/local/models/test`

Quick validation that a model works end-to-end:

```python
class TestRequest(BaseModel):
    model: str           # "qwen3:8b"
    base_url: str = "http://localhost:11434"

class TestResponse(BaseModel):
    success: bool
    response_text: str   # First ~100 chars of model response
    latency_ms: int      # Time to first token
    tokens_per_second: float
    tool_mode: str       # "native" | "json_fallback"
```

Implementation: send "Say hello in one sentence" with 1 tool definition,
measure response time, check if tool_use response works.

Frontend: show after download in onboarding or settings:
```
✅ Model test passed
   Response: "Hello! How can I help you today?"
   Speed: ~12 tok/s · Tools: native
```

---

## 6. Chat.py Integration Details

### `_make_llm()` — Full Ollama Path

```python
def _make_llm(provider, model, api_key, base_url=None):
    if provider == "ollama":
        ollama_base = base_url or "http://localhost:11434"
        config = LLMConfig(
            provider="ollama",
            model=model or "ollama_chat/qwen3:8b",
            api_key="ollama",            # LiteLLM needs non-empty
            api_base=ollama_base,
            timeout=600,
        )
        return LLMService(config)

    if provider and provider != "anthropic":
        config = LLMConfig(provider=provider, model=model, api_key=api_key)
        return LLMService(config)

    return ClaudeService(api_key=api_key)
```

### WebSocket Message — New Fields

```json
{
  "type": "message",
  "content": "Plan my week",
  "session_id": "...",
  "provider": "ollama",
  "model": "ollama_chat/qwen3:8b",
  "base_url": "http://localhost:11434"
}
```

Note: **no `api_key` field** when provider is ollama.

### Response Metadata

```json
{
  "type": "done",
  "model": "ollama_chat/qwen3:8b",
  "provider": "ollama",
  "tool_mode": "native",
  "tokens_per_second": 14.2
}
```

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ollama not running on app start | Chat fails immediately | Health check on mount; clear banner with instructions |
| Port 11434 blocked by firewall | Can't reach Ollama | Configurable base_url; error message mentions port |
| Model unloaded after idle | First response very slow | Keep-alive warm-up; "Loading model..." indicator |
| Tool calling fails on small models | Jarvis tools don't work | Tool mode badge; graceful fallback; clear UX messaging |
| Very slow generation on CPU | User thinks app is frozen | Slow response indicator with timer; suggest smaller model |
| Ollama crashes mid-generation | Partial response, then silence | WebSocket error handling; "Generation interrupted" message |
| LiteLLM format conversion fails | Broken tool responses | Try/except in tool parsing; log and skip broken tools |
| Multiple Ollama instances on different ports | Confusion | Only support one base_url at a time; configurable in settings |

---

## Tests

```python
# test_local_models_integration.py

def test_make_llm_ollama_provider()
def test_make_llm_ollama_no_api_key_needed()
def test_make_llm_ollama_custom_base_url()
def test_ollama_timeout_is_600()
def test_cloud_timeout_is_120()
def test_warm_up_endpoint()
def test_test_endpoint_returns_metrics()
def test_test_endpoint_ollama_not_running()
```

```typescript
// local-models-integration.test.ts

describe('Local model chat integration', () => {
  it('sends provider=ollama without api_key')
  it('shows slow response indicator after 10s')
  it('shows Ollama down banner when runtime unreachable')
  it('reconnect button re-probes runtime')
  it('switch to cloud button opens model selector')
  it('health polling stops when provider is not ollama')
})
```

---

## Definition of Done

- [ ] Tool mode (native/fallback) shown on model cards
- [ ] `LLMConfig` has `timeout` and `api_base` fields
- [ ] Ollama provider uses 600s timeout
- [ ] Health polling active when `activeProvider === "ollama"`
- [ ] Banner shown when Ollama goes offline during session
- [ ] Slow response indicator after 10s silence
- [ ] Warm-up endpoint keeps model loaded
- [ ] Test endpoint validates model works
- [ ] `chat.py` handles `provider == "ollama"` correctly
- [ ] WebSocket message supports `base_url` field
- [ ] Response metadata includes `tool_mode`
- [ ] StatusBar shows local model name + status
