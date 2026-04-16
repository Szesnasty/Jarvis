"""Ollama service — runtime detection, hardware profiling, model catalog & management.

Provides all backend logic for local model support:
- Hardware profiling (OS, RAM, disk, CPU, GPU detection)
- Ollama runtime detection (installed / running / version)
- Curated model catalog with hardware-based recommendations
- Model pull (proxied from Ollama API with progress streaming)
- Model selection and activation
"""

import json
import logging
import os
import platform
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Default Ollama URL ───────────────────────────────────────────────────────

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

# ── Pydantic Schemas ─────────────────────────────────────────────────────────


class HardwareProfile(BaseModel):
    os: str  # "macos" | "windows" | "linux"
    arch: str  # "arm64" | "x64"
    total_ram_gb: float
    free_disk_gb: float
    cpu_cores: int
    gpu_vendor: Optional[str] = None  # "apple" | "nvidia" | "amd" | None
    gpu_vram_gb: Optional[float] = None
    is_apple_silicon: bool = False
    tier: str = "light"  # "light" | "balanced" | "strong" | "workstation"


class RuntimeStatus(BaseModel):
    runtime: str = "ollama"
    installed: bool = False
    running: bool = False
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    version: Optional[str] = None
    reachable: bool = False


class ModelCatalogEntry(BaseModel):
    id: str
    preset: str  # "fast" | "everyday" | "balanced" | "long-docs" | "reasoning" | "code" | "best-local"
    ollama_model: str  # e.g. "qwen3:8b"
    litellm_model: str  # e.g. "ollama_chat/qwen3:8b"
    label: str
    download_size_gb: float
    context_window: str  # e.g. "40K"
    context_tokens: int
    recommended_ram_min_gb: int
    recommended_ram_max_gb: int
    min_disk_gb: float
    cpu_friendly: bool
    gpu_preferred: bool
    strengths: List[str]
    best_for: List[str]
    native_tools: bool


class ModelRecommendation(BaseModel):
    model_id: str
    preset: str
    label: str
    ollama_model: str
    litellm_model: str
    download_size_gb: float
    context_window: str
    strengths: List[str]
    best_for: List[str]
    recommended_ram: str  # e.g. "16–32 GB"
    native_tools: bool
    tool_mode: str = "limited"  # "native" | "json_fallback" | "limited"
    compatibility: str  # "great" | "good" | "warning" | "unsupported"
    score: int  # 0–100
    recommended: bool
    reason: str
    installed: bool
    active: bool


class PullRequest(BaseModel):
    model: str  # e.g. "qwen3:8b"
    base_url: str = DEFAULT_OLLAMA_BASE_URL


class SelectRequest(BaseModel):
    model_id: str
    litellm_model: str
    base_url: str = DEFAULT_OLLAMA_BASE_URL


class WarmUpRequest(BaseModel):
    model: str
    base_url: str = DEFAULT_OLLAMA_BASE_URL


class TestRequest(BaseModel):
    model: str
    base_url: str = DEFAULT_OLLAMA_BASE_URL


class TestResponse(BaseModel):
    success: bool
    response_text: str = ""
    latency_ms: int = 0
    tokens_per_second: float = 0.0
    tool_mode: str = ""  # "native" | "json_fallback" | "limited"
    error: str = ""


# ── Model Catalog ────────────────────────────────────────────────────────────

MODEL_CATALOG: List[ModelCatalogEntry] = [
    ModelCatalogEntry(
        id="qwen3-1.7b",
        preset="fast",
        ollama_model="qwen3:1.7b",
        litellm_model="ollama_chat/qwen3:1.7b",
        label="Qwen3 1.7B",
        download_size_gb=1.4,
        context_window="40K",
        context_tokens=40960,
        recommended_ram_min_gb=8,
        recommended_ram_max_gb=16,
        min_disk_gb=4,
        cpu_friendly=True,
        gpu_preferred=False,
        strengths=["fast", "multilingual", "lightweight"],
        best_for=["quick chat", "weak hardware", "testing"],
        native_tools=False,
    ),
    ModelCatalogEntry(
        id="qwen3-4b",
        preset="everyday",
        ollama_model="qwen3:4b",
        litellm_model="ollama_chat/qwen3:4b",
        label="Qwen3 4B",
        download_size_gb=2.5,
        context_window="256K",
        context_tokens=262144,
        recommended_ram_min_gb=12,
        recommended_ram_max_gb=24,
        min_disk_gb=6,
        cpu_friendly=True,
        gpu_preferred=False,
        strengths=["balanced", "multilingual", "large context"],
        best_for=["everyday chat", "multilingual tasks", "moderate hardware"],
        native_tools=False,
    ),
    ModelCatalogEntry(
        id="qwen3-8b",
        preset="balanced",
        ollama_model="qwen3:8b",
        litellm_model="ollama_chat/qwen3:8b",
        label="Qwen3 8B",
        download_size_gb=5.2,
        context_window="40K",
        context_tokens=40960,
        recommended_ram_min_gb=16,
        recommended_ram_max_gb=32,
        min_disk_gb=10,
        cpu_friendly=True,
        gpu_preferred=True,
        strengths=["universal", "multilingual", "tool calling"],
        best_for=["everyday chat", "tools", "general use"],
        native_tools=True,
    ),
    ModelCatalogEntry(
        id="ministral-3-8b",
        preset="long-docs",
        ollama_model="ministral-3:8b",
        litellm_model="ollama_chat/ministral-3:8b",
        label="Ministral 3 8B",
        download_size_gb=6.0,
        context_window="256K",
        context_tokens=262144,
        recommended_ram_min_gb=16,
        recommended_ram_max_gb=32,
        min_disk_gb=11,
        cpu_friendly=True,
        gpu_preferred=True,
        strengths=["long context", "documents", "edge deployment"],
        best_for=["long documents", "big context windows", "research"],
        native_tools=False,
    ),
    ModelCatalogEntry(
        id="gemma4-e4b",
        preset="reasoning",
        ollama_model="gemma4:e4b",
        litellm_model="ollama_chat/gemma4:e4b",
        label="Gemma 4 E4B",
        download_size_gb=9.6,
        context_window="128K",
        context_tokens=131072,
        recommended_ram_min_gb=24,
        recommended_ram_max_gb=40,
        min_disk_gb=16,
        cpu_friendly=False,
        gpu_preferred=True,
        strengths=["reasoning", "agentic", "multimodal"],
        best_for=["reasoning tasks", "agentic workflows", "analysis"],
        native_tools=True,
    ),
    ModelCatalogEntry(
        id="devstral-small-2-24b",
        preset="code",
        ollama_model="devstral-small-2:24b",
        litellm_model="ollama_chat/devstral-small-2:24b",
        label="Devstral Small 2 24B",
        download_size_gb=15.0,
        context_window="384K",
        context_tokens=393216,
        recommended_ram_min_gb=32,
        recommended_ram_max_gb=64,
        min_disk_gb=22,
        cpu_friendly=False,
        gpu_preferred=True,
        strengths=["coding", "repo exploration", "multi-file edits"],
        best_for=["code generation", "software engineering", "repo work"],
        native_tools=True,
    ),
    ModelCatalogEntry(
        id="gemma4-27b",
        preset="best-local",
        ollama_model="gemma4:27b",
        litellm_model="ollama_chat/gemma4:27b",
        label="Gemma 4 27B",
        download_size_gb=18.0,
        context_window="256K",
        context_tokens=262144,
        recommended_ram_min_gb=32,
        recommended_ram_max_gb=64,
        min_disk_gb=26,
        cpu_friendly=False,
        gpu_preferred=True,
        strengths=["premium", "reasoning", "generalist", "multimodal"],
        best_for=["best quality", "complex tasks", "premium local"],
        native_tools=True,
    ),
]

# Index for fast lookup
_CATALOG_BY_ID: Dict[str, ModelCatalogEntry] = {m.id: m for m in MODEL_CATALOG}


def _tool_mode_for(entry: ModelCatalogEntry) -> str:
    """Derive tool_mode from catalog entry flags."""
    if entry.native_tools:
        return "native"
    # Small models (< 3B params, heuristic: download < 2 GB) → limited
    if entry.download_size_gb < 2.0:
        return "limited"
    return "json_fallback"


def get_catalog() -> List[ModelCatalogEntry]:
    """Return the full model catalog."""
    return MODEL_CATALOG


def get_model_by_id(model_id: str) -> Optional[ModelCatalogEntry]:
    """Look up a model by its catalog ID."""
    return _CATALOG_BY_ID.get(model_id)


# ── Hardware Probe ───────────────────────────────────────────────────────────


def _detect_gpu() -> Tuple[Optional[str], Optional[float]]:
    """Detect GPU vendor and VRAM. Returns (vendor, vram_gb)."""
    system = platform.system()

    if system == "Darwin":
        # Apple Silicon has unified memory — GPU vendor is "apple",
        # VRAM is effectively the total RAM (shared).
        if platform.machine() == "arm64":
            return "apple", None
        return None, None

    # Try nvidia-smi for NVIDIA GPUs
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            result = subprocess.run(
                [nvidia_smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                vram_mb = float(result.stdout.strip().split("\n")[0])
                return "nvidia", round(vram_mb / 1024, 1)
        except (subprocess.TimeoutExpired, ValueError, OSError):
            pass

    return None, None


def _get_total_ram_gb() -> float:
    """Get total system RAM in GB."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except ImportError:
        # Fallback without psutil
        system = platform.system()
        if system == "Darwin":
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    return round(int(result.stdout.strip()) / (1024 ** 3), 1)
            except (subprocess.TimeoutExpired, ValueError, OSError):
                pass
        elif system == "Linux":
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            return round(kb / (1024 ** 2), 1)
            except (IOError, ValueError):
                pass
        return 0.0


def _get_free_disk_gb() -> float:
    """Get free disk space on the root volume in GB."""
    try:
        usage = shutil.disk_usage("/")
        return round(usage.free / (1024 ** 3), 1)
    except OSError:
        return 0.0


def classify_tier(ram_gb: float, gpu_vendor: Optional[str] = None) -> str:
    """Classify hardware into a tier based on RAM and GPU."""
    if ram_gb >= 48:
        return "workstation"
    if ram_gb >= 32:
        return "strong"
    if ram_gb >= 16:
        return "balanced"
    return "light"


def probe_hardware() -> HardwareProfile:
    """Detect local hardware profile."""
    system = platform.system().lower()
    os_name = {
        "darwin": "macos",
        "linux": "linux",
        "windows": "windows",
    }.get(system, system)

    arch = platform.machine()
    # Normalize arch
    if arch in ("AMD64", "x86_64"):
        arch = "x64"

    total_ram = _get_total_ram_gb()
    free_disk = _get_free_disk_gb()
    cpu_cores = os.cpu_count() or 1
    gpu_vendor, gpu_vram = _detect_gpu()
    is_apple_silicon = (os_name == "macos" and platform.machine() == "arm64")
    tier = classify_tier(total_ram, gpu_vendor)

    return HardwareProfile(
        os=os_name,
        arch=arch,
        total_ram_gb=total_ram,
        free_disk_gb=free_disk,
        cpu_cores=cpu_cores,
        gpu_vendor=gpu_vendor,
        gpu_vram_gb=gpu_vram,
        is_apple_silicon=is_apple_silicon,
        tier=tier,
    )


# ── Runtime Probe ────────────────────────────────────────────────────────────


async def probe_runtime(base_url: str = DEFAULT_OLLAMA_BASE_URL) -> RuntimeStatus:
    """Check if Ollama is installed and running."""
    status = RuntimeStatus(base_url=base_url)

    # 1. Check if ollama binary exists
    ollama_path = shutil.which("ollama")
    status.installed = ollama_path is not None

    # 2. Try to reach the API
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{base_url}/api/version")
            if resp.status_code == 200:
                status.running = True
                status.reachable = True
                data = resp.json()
                status.version = data.get("version")
            else:
                # Some Ollama versions return 200 on root but not /api/version
                # Try the root endpoint as fallback
                resp2 = await client.get(base_url)
                if resp2.status_code == 200:
                    status.running = True
                    status.reachable = True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        pass
    except Exception as exc:
        logger.debug("Ollama probe unexpected error: %s", exc)

    return status


# ── Installed Models ─────────────────────────────────────────────────────────


async def list_installed_models(base_url: str = DEFAULT_OLLAMA_BASE_URL) -> List[Dict[str, Any]]:
    """List models currently downloaded in Ollama via GET /api/tags."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.debug("Cannot reach Ollama at %s to list models", base_url)
    except Exception as exc:
        logger.debug("Error listing Ollama models: %s", exc)
    return []


def _is_model_installed(ollama_model: str, installed: List[Dict[str, Any]]) -> bool:
    """Check if a model name matches any installed model."""
    # Ollama model names can be "qwen3:8b" or "qwen3:latest"
    # Installed models have "name" field like "qwen3:8b"
    target = ollama_model.lower()
    for m in installed:
        name = m.get("name", "").lower()
        if name == target:
            return True
        # Also check without tag (e.g. "qwen3" matches "qwen3:latest")
        if ":" in target:
            base = target.split(":")[0]
            if name == base or name.startswith(base + ":"):
                # Only match if tags align
                pass
    return False


# ── Recommendation Engine ────────────────────────────────────────────────────


def score_model(
    model: ModelCatalogEntry,
    hw: HardwareProfile,
    installed_names: List[str],
    active_model_id: Optional[str] = None,
) -> ModelRecommendation:
    """Score a model against hardware profile and return a recommendation."""

    # Disk check — hard block
    required_disk = model.download_size_gb * 1.25 + 2
    if hw.free_disk_gb > 0 and hw.free_disk_gb < required_disk:
        return ModelRecommendation(
            model_id=model.id,
            preset=model.preset,
            label=model.label,
            ollama_model=model.ollama_model,
            litellm_model=model.litellm_model,
            download_size_gb=model.download_size_gb,
            context_window=model.context_window,
            strengths=model.strengths,
            best_for=model.best_for,
            recommended_ram="%d\u2013%d GB" % (model.recommended_ram_min_gb, model.recommended_ram_max_gb),
            native_tools=model.native_tools,
            tool_mode=_tool_mode_for(model),
            compatibility="unsupported",
            score=0,
            recommended=False,
            reason="Not enough disk space (need %.1f GB free)" % required_disk,
            installed=model.ollama_model.lower() in installed_names,
            active=(model.id == active_model_id),
        )

    # RAM check
    ram = hw.total_ram_gb
    model_size = model.download_size_gb
    has_gpu = hw.gpu_vendor is not None

    if has_gpu or hw.is_apple_silicon:
        # GPU / Apple Silicon — unified memory or dedicated VRAM
        usable = hw.gpu_vram_gb if hw.gpu_vram_gb else ram
        if usable >= 2.0 * model_size:
            compat = "great"
            base_score = 90
        elif usable >= 1.5 * model_size:
            compat = "good"
            base_score = 70
        elif usable >= 1.2 * model_size:
            compat = "warning"
            base_score = 40
        else:
            compat = "unsupported"
            base_score = 0
    else:
        # CPU-only
        if ram >= 3.0 * model_size:
            compat = "great"
            base_score = 90
        elif ram >= 2.5 * model_size:
            compat = "good"
            base_score = 70
        elif ram >= 2.0 * model_size:
            compat = "warning"
            base_score = 40
        else:
            compat = "unsupported"
            base_score = 0

    # Bonuses
    score = base_score
    # cpu_friendly bonus only for pure CPU machines (not Apple Silicon, which has unified memory GPU)
    if model.cpu_friendly and not has_gpu and not hw.is_apple_silicon:
        score += 10
    if ram < model.recommended_ram_min_gb:
        score -= 20
    # On strong hardware (32+ GB), prefer higher-context models so they rank above tiny ones
    if hw.tier in ("strong", "workstation") and model.context_tokens >= 131072:
        score += 8
    # Clamp
    score = max(0, min(100, score))

    # Reason
    if compat == "great":
        reason_parts = ["Recommended"]
        if hw.is_apple_silicon:
            reason_parts.append("fits your %.0f GB unified memory" % ram)
        elif has_gpu:
            reason_parts.append("fits your %.0f GB RAM with GPU" % ram)
        else:
            reason_parts.append("fits your %.0f GB RAM" % ram)
        reason = " \u2014 ".join(reason_parts)
    elif compat == "good":
        reason = "Compatible with your hardware"
    elif compat == "warning":
        reason = "May be slow \u2014 your RAM is near the minimum"
    else:
        reason = "Not enough resources for this model"

    installed = model.ollama_model.lower() in installed_names

    return ModelRecommendation(
        model_id=model.id,
        preset=model.preset,
        label=model.label,
        ollama_model=model.ollama_model,
        litellm_model=model.litellm_model,
        download_size_gb=model.download_size_gb,
        context_window=model.context_window,
        strengths=model.strengths,
        best_for=model.best_for,
        recommended_ram="%d\u2013%d GB" % (model.recommended_ram_min_gb, model.recommended_ram_max_gb),
        native_tools=model.native_tools,
        tool_mode=_tool_mode_for(model),
        compatibility=compat,
        score=score,
        recommended=False,  # Set later by build_catalog
        reason=reason,
        installed=installed,
        active=(model.id == active_model_id),
    )


async def build_catalog(
    hw: HardwareProfile,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    active_model_id: Optional[str] = None,
) -> List[ModelRecommendation]:
    """Build the full model catalog with recommendations."""
    installed = await list_installed_models(base_url)
    installed_names = [m.get("name", "").lower() for m in installed]

    recommendations = []
    for model in MODEL_CATALOG:
        rec = score_model(model, hw, installed_names, active_model_id)
        recommendations.append(rec)

    # Sort by score descending
    recommendations.sort(key=lambda r: r.score, reverse=True)

    # Mark top 3 non-unsupported as recommended
    count = 0
    for rec in recommendations:
        if rec.compatibility != "unsupported" and count < 3:
            rec.recommended = True
            count += 1

    return recommendations


# ── Model Pull (Streaming) ──────────────────────────────────────────────────

async def pull_model_stream(model: str, base_url: str = DEFAULT_OLLAMA_BASE_URL):
    """Pull a model from Ollama, yielding SSE-formatted progress lines.

    Yields strings like: 'data: {"status": "pulling manifest"}\n\n'
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/pull",
            json={"name": model, "stream": True},
        ) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                yield 'data: %s\n\n' % json.dumps({
                    "status": "error",
                    "error": "Ollama returned status %d: %s" % (resp.status_code, error_body.decode()[:200]),
                })
                return

            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    yield "data: %s\n\n" % json.dumps(data)
                except json.JSONDecodeError:
                    continue

    yield 'data: {"status": "done"}\n\n'


# ── Model Delete ─────────────────────────────────────────────────────────────


async def delete_model(model: str, base_url: str = DEFAULT_OLLAMA_BASE_URL) -> bool:
    """Delete a model from Ollama. Returns True on success."""
    import json as _json
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            resp = await client.request(
                "DELETE",
                f"{base_url}/api/delete",
                content=_json.dumps({"name": model}),
                headers={"Content-Type": "application/json"},
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# ── Model Warm-up ────────────────────────────────────────────────────────────


async def warm_up_model(model: str, base_url: str = DEFAULT_OLLAMA_BASE_URL) -> bool:
    """Send a tiny prompt to keep model loaded in Ollama memory."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": "30m",
                },
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# ── Model Test ───────────────────────────────────────────────────────────────


async def test_model(model: str, base_url: str = DEFAULT_OLLAMA_BASE_URL) -> TestResponse:
    """Quick validation that a model works end-to-end."""
    import time

    # Determine tool_mode from catalog (if known)
    catalog_entry = None
    for entry in MODEL_CATALOG:
        if entry.ollama_model == model:
            catalog_entry = entry
            break
    tool_mode = _tool_mode_for(catalog_entry) if catalog_entry else "json_fallback"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            start = time.monotonic()
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
                    "stream": False,
                },
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code != 200:
                return TestResponse(
                    success=False,
                    error="Ollama returned status %d" % resp.status_code,
                )

            data = resp.json()
            message = data.get("message", {})
            text = message.get("content", "")[:200]

            # Calculate tokens/second from Ollama's metrics
            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 0)
            tps = 0.0
            if eval_duration_ns > 0 and eval_count > 0:
                tps = round(eval_count / (eval_duration_ns / 1e9), 1)

            return TestResponse(
                success=True,
                response_text=text,
                latency_ms=elapsed_ms,
                tokens_per_second=tps,
                tool_mode=tool_mode,
            )
    except httpx.TimeoutException:
        return TestResponse(success=False, error="Request timed out (120s)")
    except httpx.ConnectError:
        return TestResponse(success=False, error="Cannot connect to Ollama")
    except Exception as exc:
        return TestResponse(success=False, error=str(exc)[:200])


# ── Active Model Config ─────────────────────────────────────────────────────


def get_active_local_model() -> Optional[Dict[str, str]]:
    """Read the active local model from workspace config.json."""
    from config import get_settings

    settings = get_settings()
    config_path = settings.workspace_path / "app" / "config.json"
    if not config_path.exists():
        return None
    try:
        with open(config_path) as f:
            config = json.load(f)
        local = config.get("local_model")
        if local and local.get("active"):
            return local
    except (json.JSONDecodeError, IOError):
        pass
    return None


def set_active_local_model(
    model_id: str,
    litellm_model: str,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> None:
    """Write the active local model to workspace config.json."""
    from config import get_settings

    settings = get_settings()
    config_path = settings.workspace_path / "app" / "config.json"
    config: Dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    config["local_model"] = {
        "active": True,
        "model_id": model_id,
        "litellm_model": litellm_model,
        "base_url": base_url,
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def clear_active_local_model() -> None:
    """Remove the active local model from workspace config.json."""
    from config import get_settings

    settings = get_settings()
    config_path = settings.workspace_path / "app" / "config.json"
    if not config_path.exists():
        return
    try:
        with open(config_path) as f:
            config = json.load(f)
        if "local_model" in config:
            config["local_model"]["active"] = False
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
    except (json.JSONDecodeError, IOError):
        pass
