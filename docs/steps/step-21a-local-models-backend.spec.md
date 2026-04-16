# Step 21a — Local Models: Backend (Ollama Service + API)

> **Goal**: Add Ollama runtime detection, hardware profiling, model catalog
> with hardware-based recommendations, and model pull/management endpoints.
> This is the backend foundation for local model support.

**Status**: ✅ Complete
**Depends on**: Step 18b (LiteLLM multi-provider backend)
**Effort**: ~3 days
**Branch**: `feat/local-models-backend`

---

## Why This Matters

Jarvis currently requires a cloud API key (Anthropic, OpenAI, Google).
Many users want to run AI **fully locally** — for privacy, cost, or offline use.
Ollama is the most popular local runtime, and LiteLLM already supports it
via the `ollama_chat/` prefix. This step adds the backend plumbing:
detect hardware, detect Ollama, recommend models, pull them, and expose
everything through REST endpoints.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `ollama_service.py` | Runtime probe, hardware detection, model pull, model listing, recommendations |
| `local_models.py` router | REST endpoints for all local model operations |
| Model catalog | Static registry of 7 curated model presets with metadata |
| Hardware probe | OS, RAM, disk, CPU, GPU/Apple Silicon detection |
| Runtime probe | Ollama installed/running/reachable detection |
| Recommendation engine | Score models against hardware profile |
| Model pull with streaming | SSE stream wrapping Ollama's `POST /api/pull` |
| Model selection | Set active local model in workspace config |
| LLM integration | `_make_llm()` in chat.py handles `provider == "ollama"` |

**What this step does NOT cover**:
- Frontend UI (step 21b)
- Onboarding flow changes (step 21c)
- Tool calling degradation handling (step 21d)

---

## File Structure

```
backend/
  services/
    ollama_service.py              # NEW — all Ollama + hardware logic
  routers/
    local_models.py                # NEW — REST endpoints
  routers/chat.py                  # MODIFY — add ollama provider path
  services/llm_service.py          # MODIFY — ollama config support
  tests/
    test_local_models.py           # NEW — unit + integration tests
```

---

## Model Catalog (Static v1)

Seven curated presets. Sizes and context windows from Ollama public catalog.

| Preset | Model | LiteLLM ID | Size | Context | Best RAM | Use Case |
|--------|-------|------------|------|---------|----------|----------|
| **Fast** | `qwen3:1.7b` | `ollama_chat/qwen3:1.7b` | 1.4 GB | 40K | 8–16 GB | Weak laptops, quick responses |
| **Everyday** | `qwen3:4b` | `ollama_chat/qwen3:4b` | 2.5 GB | 256K | 12–24 GB | Best light default, big context |
| **Balanced** | `qwen3:8b` | `ollama_chat/qwen3:8b` | 5.2 GB | 40K | 16–32 GB | Universal everyday use |
| **Long Docs** | `ministral-3:8b` | `ollama_chat/ministral-3:8b` | 6.0 GB | 256K | 16–32 GB | Long documents, big context |
| **Reasoning** | `gemma4:e4b` | `ollama_chat/gemma4:e4b` | 9.6 GB | 128K | 24–40 GB | Reasoning, agentic workflows |
| **Code** | `devstral-small-2:24b` | `ollama_chat/devstral-small-2:24b` | 15 GB | 384K | 32–64 GB | Code, repo work, file edits |
| **Best Local** | `gemma4:26b` | `ollama_chat/gemma4:26b` | 18 GB | 256K | 32–64 GB | Premium local generalist |

```python
MODEL_CATALOG = [
    {
        "id": "qwen3-1.7b",
        "preset": "fast",
        "ollama_model": "qwen3:1.7b",
        "litellm_model": "ollama_chat/qwen3:1.7b",
        "label": "Qwen3 1.7B",
        "download_size_gb": 1.4,
        "context_window": "40K",
        "context_tokens": 40960,
        "recommended_ram_min_gb": 8,
        "recommended_ram_max_gb": 16,
        "min_disk_gb": 4,
        "cpu_friendly": True,
        "gpu_preferred": False,
        "strengths": ["fast", "multilingual", "lightweight"],
        "best_for": ["quick chat", "weak hardware", "testing"],
        "native_tools": False,
    },
    # ... remaining 6 entries follow same shape
]
```

---

## Hardware Probe

### Response Schema

```python
class HardwareProfile(BaseModel):
    os: str               # "macos" | "windows" | "linux"
    arch: str             # "arm64" | "x64"
    total_ram_gb: float
    free_disk_gb: float
    cpu_cores: int
    gpu_vendor: Optional[str]     # "apple" | "nvidia" | "amd" | None
    gpu_vram_gb: Optional[float]
    is_apple_silicon: bool
    tier: str             # "light" | "balanced" | "strong" | "workstation"
```

### Tier Classification

```python
def classify_tier(ram_gb: float, gpu_vendor: Optional[str]) -> str:
    if ram_gb >= 48:
        return "workstation"
    if ram_gb >= 32:
        return "strong"
    if ram_gb >= 16:
        return "balanced"
    return "light"
```

### Implementation Notes

- Use `platform.system()`, `platform.machine()` for OS/arch
- Use `psutil.virtual_memory()` for RAM (add `psutil` to requirements.txt)
- Use `shutil.disk_usage()` for free disk
- Use `os.cpu_count()` for cores
- Apple Silicon detection: `platform.machine() == "arm64"` on macOS
- GPU detection: parse `system_profiler SPDisplaysDataType` on macOS,
  `nvidia-smi` on Linux/Windows
- **Python 3.9 compatible** — no match/case, no `X | None` union syntax

---

## Runtime Probe

### Response Schema

```python
class RuntimeStatus(BaseModel):
    runtime: str          # "ollama"
    installed: bool
    running: bool
    base_url: str         # default "http://localhost:11434"
    version: Optional[str]
    reachable: bool
```

### Implementation

```python
async def probe_runtime(base_url: str = "http://localhost:11434") -> RuntimeStatus:
    """Check if Ollama is installed and running."""
    import httpx

    status = RuntimeStatus(
        runtime="ollama",
        installed=False,
        running=False,
        base_url=base_url,
        version=None,
        reachable=False,
    )

    # 1. Check if ollama binary exists
    ollama_path = shutil.which("ollama")
    status.installed = ollama_path is not None

    # 2. Try to reach the API
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/api/version")
            if resp.status_code == 200:
                status.running = True
                status.reachable = True
                data = resp.json()
                status.version = data.get("version")
    except (httpx.ConnectError, httpx.TimeoutException):
        pass

    return status
```

---

## Recommendation Engine

### Scoring Algorithm

For each model in catalog, compute a compatibility score:

```
1. DISK CHECK — hard block
   if free_disk < download_size * 1.25 + 2 GB → unsupported

2. RAM CHECK
   CPU-only:
     ram >= 3x model_size → "great"
     ram >= 2.5x model_size → "good"
     ram >= 2x model_size → "warning"
     else → "unsupported"

   GPU / Apple Silicon:
     usable_memory >= 2x model_size → "great"
     usable_memory >= 1.5x model_size → "good"
     usable_memory >= 1.2x model_size → "warning"
     else → "unsupported"

3. SCORE (0–100)
   Base score from compatibility (great=90, good=70, warning=40)
   +10 bonus if model.cpu_friendly and no GPU
   +5 bonus for matching use case (code/docs/reasoning)
   -20 penalty if ram < recommended_ram_min

4. RECOMMENDED flag
   Top 3 models by score with compatibility != "unsupported"

5. REASON string
   "Recommended — fits your 32 GB RAM with Apple Silicon"
   "Warning — may be slow, your RAM is below recommended minimum"
   "Unsupported — not enough disk space"
```

### Response Schema

```python
class ModelRecommendation(BaseModel):
    model_id: str
    preset: str
    label: str
    download_size_gb: float
    context_window: str
    strengths: List[str]
    best_for: List[str]
    recommended_ram: str          # "16–32 GB"
    native_tools: bool
    compatibility: str            # "great" | "good" | "warning" | "unsupported"
    score: int                    # 0–100
    recommended: bool
    reason: str
    installed: bool               # already pulled in Ollama
    active: bool                  # currently selected model
```

---

## API Endpoints

### `GET /api/local/hardware`

Returns `HardwareProfile`. No auth required (local data only).

### `GET /api/local/runtime`

Returns `RuntimeStatus`. Probes Ollama at configured base_url.

### `GET /api/local/models/catalog`

Returns list of `ModelRecommendation`. Combines:
- Static model catalog
- Hardware profile (for scoring)
- Installed models from Ollama (`GET /api/tags`)

Query params:
- `base_url` (optional, default `http://localhost:11434`)

### `GET /api/local/models/installed`

Returns models currently downloaded in Ollama.
Proxies `GET {base_url}/api/tags`.

### `POST /api/local/models/pull`

**Streams progress via SSE (Server-Sent Events).**

Request body:
```json
{
  "model": "qwen3:8b",
  "base_url": "http://localhost:11434"
}
```

Implementation:
```python
@router.post("/api/local/models/pull")
async def pull_model(req: PullRequest):
    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{req.base_url}/api/pull",
                json={"name": req.model, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    data = json.loads(line)
                    yield f"data: {json.dumps(data)}\n\n"
        yield "data: {\"status\": \"done\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )
```

Progress events from Ollama:
```json
{"status": "pulling manifest"}
{"status": "pulling abc123", "digest": "sha256:abc...", "total": 5200000000, "completed": 1200000000}
{"status": "verifying sha256 digest"}
{"status": "writing manifest"}
{"status": "success"}
```

### `POST /api/local/models/select`

Set active local model in workspace config.

Request body:
```json
{
  "model_id": "qwen3-8b",
  "litellm_model": "ollama_chat/qwen3:8b",
  "base_url": "http://localhost:11434"
}
```

Saves to `config.json`:
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

---

## Chat Integration

### Modify `_make_llm()` in `chat.py`

```python
def _make_llm(provider, model, api_key):
    if provider == "ollama":
        config = LLMConfig(
            provider="ollama",
            model=model or "ollama_chat/qwen3:8b",
            api_key="ollama",          # LiteLLM needs non-empty string
            api_base="http://localhost:11434",
        )
        return LLMService(config)

    if provider and provider != "anthropic":
        config = LLMConfig(provider=provider, model=model, api_key=api_key)
        return LLMService(config)

    return ClaudeService(api_key=api_key)
```

### Modify `LLMConfig`

Add optional `api_base` field:
```python
@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    api_base: Optional[str] = None  # NEW — for Ollama
```

Pass `api_base` to LiteLLM `acompletion()` call.

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ollama not running when user returns | Model requests fail silently | Runtime probe on every chat start; clear error message in UI |
| Port 11434 occupied by another service | Connection fails | `base_url` configurable from day one; settings field |
| `psutil` not available | Hardware probe crashes | Graceful fallback: return unknown tier, let user pick manually |
| Slow CPU inference (2 tok/s) | User thinks app is broken | Increase timeout for ollama provider; show "Local models are slower" hint |
| Ollama API changes | Endpoints break | Pin to stable Ollama API; wrap all calls in try/except with clear errors |
| Python 3.9 compatibility | match/case or union syntax fails | Enforce `if/elif` chains, `Optional[X]` syntax |

---

## Tests

```python
# test_local_models.py

# Unit tests
def test_classify_tier_light()        # 8 GB → light
def test_classify_tier_balanced()     # 16 GB → balanced
def test_classify_tier_strong()       # 32 GB → strong
def test_classify_tier_workstation()  # 64 GB → workstation

def test_score_model_great_compat()   # 32 GB + qwen3:1.7b → great
def test_score_model_warning()        # 8 GB + gemma4:26b → warning
def test_score_model_unsupported()    # 4 GB disk + 18 GB model → unsupported
def test_recommend_top_3()            # Verify top 3 selection logic

def test_hardware_probe_returns_valid_profile()
def test_runtime_probe_ollama_not_running()
def test_runtime_probe_ollama_running()

# Integration tests (require Ollama running)
def test_catalog_endpoint_returns_models()
def test_pull_endpoint_streams_progress()
def test_select_endpoint_saves_config()
```

---

## Dependencies

Add to `requirements.txt`:
```
psutil>=5.9.0
```

`httpx` is already in requirements (used by test client).

---

## Definition of Done

- [ ] `ollama_service.py` with hardware probe, runtime probe, catalog, scoring, pull
- [ ] `local_models.py` router with 5 endpoints
- [ ] `chat.py` handles `provider == "ollama"` via `_make_llm()`
- [ ] `LLMConfig` supports `api_base`
- [ ] Unit tests pass for scoring, tier classification, probe mocking
- [ ] Model catalog has 7 entries with correct metadata
- [ ] SSE streaming works for model pull
- [ ] `psutil` added to requirements.txt
- [ ] All code Python 3.9 compatible
