# Local Models

Run Jarvis with on-device AI via Ollama — no API key required.

## Summary

The local models feature adds support for running Jarvis with locally-hosted LLMs via Ollama. It provides hardware detection, a curated catalog of 7 model presets with hardware-based recommendations, model download with streaming progress, seamless integration with the existing multi-provider chat pipeline via LiteLLM, tool calling mode detection per model, runtime health monitoring with reconnection flow, and slow response indicators for local inference.

## How It Works

### Hardware Probe

`probe_hardware()` detects the user's system specs (OS, RAM, disk, CPU cores, GPU vendor/VRAM, Apple Silicon) and classifies them into a tier: light (8–16 GB), balanced (16–32 GB), strong (32–48 GB), or workstation (48+ GB). Uses `psutil` for RAM with fallback to OS-native commands.

### Runtime Probe

`probe_runtime()` checks if Ollama is installed (via `shutil.which`) and running (via `GET /api/version` on the configured base URL). Returns installation status, version, and reachability.

### Model Catalog

Seven curated presets cover the spectrum from weak laptops to workstations:

| Preset | Model | Size | Context | Best RAM |
|--------|-------|------|---------|----------|
| Fast | qwen3:1.7b | 1.4 GB | 40K | 8–16 GB |
| Everyday | qwen3:4b | 2.5 GB | 256K | 12–24 GB |
| Balanced | qwen3:8b | 5.2 GB | 40K | 16–32 GB |
| Long Docs | ministral-3:8b | 6.0 GB | 256K | 16–32 GB |
| Reasoning | gemma4:e4b | 9.6 GB | 128K | 24–40 GB |
| Code | devstral-small-2:24b | 15 GB | 384K | 32–64 GB |
| Best Local | gemma4:27b | 18 GB | 256K | 32–64 GB |

### Recommendation Engine

`score_model()` computes a compatibility score (0–100) for each model based on:
- **Disk check**: hard block if not enough space
- **RAM check**: different thresholds for CPU-only vs GPU/Apple Silicon
- **Bonuses**: CPU-friendly models on CPU-only machines, use-case matching

`build_catalog()` scores all models, sorts by score, and marks top 3 as recommended.

### Tool Calling Mode

Each model gets a `tool_mode` classification:
- **native** — model supports native function calling (e.g. qwen3:8b, gemma4 variants)
- **json_fallback** — model doesn't natively support tools but can use JSON-mode fallback via LiteLLM (e.g. qwen3:4b, ministral-3:8b)
- **limited** — very small models (< 2 GB) that may not reliably execute tools (e.g. qwen3:1.7b)

`_tool_mode_for()` derives tool_mode from the catalog entry's `native_tools` flag and `download_size_gb`.

### Runtime Health Monitoring

`useLocalModels.ts` provides `startHealthPolling()` / `stopHealthPolling()` that periodically probe the Ollama runtime. When `activeProvider === 'ollama'`, the main chat page starts polling every 30s. If Ollama becomes unreachable, `ollamaDown` state triggers a banner in ChatPanel with Reconnect/Switch to Cloud options.

### Slow Response Indicator

`useChat.ts` starts a timer when sending a message with the ollama provider. After 10s with no text_delta, it shows "Local model is loading...". After 30s, it shows an extended message suggesting a smaller model. Cleared immediately when the first text arrives or the response completes.

### Model Pull

`pull_model_stream()` proxies Ollama's `POST /api/pull` with `stream: true` and converts the progress events into SSE format for the frontend.

### Chat Integration

`_make_llm()` in `chat.py` routes `provider == "ollama"` to `LLMService` with `api_base` set to the Ollama URL and a 600s timeout (vs 120s for cloud). No API key is required — the sentinel value `"ollama"` satisfies LiteLLM's non-empty requirement.

## Key Files

| File | Purpose |
|------|---------|
| [ollama_service.py](../../backend/services/ollama_service.py) | All Ollama logic: hardware/runtime probes, catalog, scoring, pull, config |
| [local_models.py](../../backend/routers/local_models.py) | REST API endpoints for local model management |
| [llm_service.py](../../backend/services/llm_service.py) | LLMConfig extended with `api_base` and `timeout`; model resolution for ollama |
| [chat.py](../../backend/routers/chat.py) | `_make_llm()` handles ollama provider; `base_url` passed through WS messages |
| [test_local_models.py](../../backend/tests/test_local_models.py) | 45 tests covering scoring, probes, config, routing |
| [useLocalModels.ts](../../frontend/app/composables/useLocalModels.ts) | Frontend composable: hardware/runtime/catalog state, pull SSE, model selection |
| [OllamaStatus.vue](../../frontend/app/components/OllamaStatus.vue) | Runtime status card (not installed / not running / running) with hardware info |
| [LocalModelCard.vue](../../frontend/app/components/LocalModelCard.vue) | Model recommendation card with compatibility badge, tool mode badge, download/use actions |
| [PullProgress.vue](../../frontend/app/components/PullProgress.vue) | Download progress bar with percentage and byte counts |
| [OnboardingLocalFlow.vue](../../frontend/app/components/OnboardingLocalFlow.vue) | Local model setup wizard for onboarding (hardware detect, Ollama check, recommend, download) |
| [test_local_models_integration.py](../../backend/tests/test_local_models_integration.py) | 22 tests: tool_mode, timeouts, warm-up, test endpoint, catalog |
| [useLocalModelsIntegration.test.ts](../../frontend/tests/composables/useLocalModelsIntegration.test.ts) | 6 tests: ollama chat, slow indicator, health polling |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/local/hardware` | GET | Hardware profile (RAM, disk, CPU, GPU, tier) |
| `/api/local/runtime` | GET | Ollama status (installed, running, version) |
| `/api/local/models/catalog` | GET | Model catalog with recommendations |
| `/api/local/models/installed` | GET | Models downloaded in Ollama |
| `/api/local/models/pull` | POST | Download model (SSE progress stream) |
| `/api/local/models/select` | POST | Set active local model |
| `/api/local/models/{name}` | DELETE | Remove model from Ollama |
| `/api/local/models/test` | POST | Quick model validation (latency, tok/s) |
| `/api/local/models/warm-up` | POST | Keep model loaded in memory |

## Gotchas

- Ollama must be running separately — Jarvis doesn't start it
- Local models on CPU can be very slow (2–10 tok/s); 600s timeout is intentional
- Not all models support native function calling; `tool_mode` field in catalog classifies support level
- `done` event includes `tool_mode` for ollama provider so frontend can display tool support info
- `psutil` is required for hardware probe; falls back to OS commands if missing
- `api_base` must be passed to LiteLLM via `acompletion()` kwargs
- Health polling runs every 30s only when provider is ollama; stopped on unmount or provider change
