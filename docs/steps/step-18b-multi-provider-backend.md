# Step 18b — Multi-Provider Backend: LiteLLM Integration

> **Goal**: Replace the Anthropic-only `ClaudeService` with a multi-provider
> backend powered by LiteLLM. Accept API keys from the frontend per-request.
> Support Anthropic, OpenAI, and Google AI with unified streaming.

**Status**: ⬜ Not started
**Depends on**: Step 18a (frontend must send `provider` + `api_key` in WS messages)

---

## Core Principles

1. **Backend never stores multi-provider keys** — key arrives in WS message, used for one request, discarded
2. **Anthropic fallback** — if no key in message, fall back to server-stored Anthropic key (backward compat)
3. **Unified interface** — `LLMService` replaces `ClaudeService` while keeping the same `StreamEvent` protocol
4. **LiteLLM handles provider differences** — message format, tool calling, streaming API all normalized
5. **Model specified per-request** — frontend sends `model` alongside `provider` + `api_key`

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `llm_service.py` | New unified LLM service wrapping LiteLLM |
| `claude.py` refactor | Keep as thin Anthropic-specific adapter or replace with `llm_service.py` |
| Chat WS handler | Accept `provider`, `api_key`, `model` from WS message |
| Duel support | `council.py` uses `LLMService` instead of `ClaudeService` |
| Provider validation | Validate provider/model combinations |
| Cost tracking | Unified token counting via LiteLLM's `model_cost` |

**What this step does NOT cover** (deferred to 18c):
- Model selector UI in chat
- Per-specialist model config
- Model persistence in user preferences

---

## File Structure

```
backend/
  services/
    llm_service.py            # NEW — LLMService (replaces ClaudeService)
    claude.py                  # MODIFY — thin wrapper or deprecated
    council.py                 # MODIFY — use LLMService
    token_tracking.py          # MODIFY — unified cost per provider
  routers/
    chat.py                    # MODIFY — parse provider/key/model from WS msg
  requirements.txt             # MODIFY — add litellm
  tests/
    test_llm_service.py        # NEW
    test_chat_provider.py      # NEW — multi-provider WS tests
```

---

## Data Models

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMConfig:
    """Per-request LLM configuration."""
    provider: str              # "anthropic" | "openai" | "google"
    model: str                 # "claude-sonnet-4-20250514" | "gpt-4o" | "gemini-2.5-flash"
    api_key: str               # raw key from frontend
    max_tokens: int = 4096
    temperature: float = 0.7

# Provider → LiteLLM model prefix mapping
PROVIDER_MODEL_MAP = {
    "anthropic": "",                  # LiteLLM uses raw model name for Anthropic
    "openai": "",                     # LiteLLM uses raw model name for OpenAI
    "google": "gemini/",             # LiteLLM prefix for Google AI
}

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.5-flash",
}
```

---

## LLMService

```python
import litellm
from services.claude import StreamEvent  # reuse existing event type

class LLMService:
    """Unified LLM service wrapping LiteLLM for multi-provider support."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._litellm_model = self._resolve_model()

    def _resolve_model(self) -> str:
        """Map provider + model to LiteLLM model string."""
        prefix = PROVIDER_MODEL_MAP.get(self.config.provider, "")
        return f"{prefix}{self.config.model}"

    async def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
    ) -> AsyncIterator[StreamEvent]:
        """Stream response — same interface as ClaudeService."""
        try:
            # LiteLLM uses OpenAI-compatible format
            litellm_messages = [{"role": "system", "content": system_prompt}] + messages

            kwargs = {
                "model": self._litellm_model,
                "messages": litellm_messages,
                "max_tokens": self.config.max_tokens,
                "stream": True,
                "api_key": self.config.api_key,
            }

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            response = await litellm.acompletion(**kwargs)

            async for chunk in response:
                event = self._process_chunk(chunk)
                if event:
                    yield event

            yield StreamEvent(type="done")

        except litellm.AuthenticationError:
            yield StreamEvent(type="error", content="Invalid API key. Check your key in Settings.")
        except litellm.RateLimitError:
            yield StreamEvent(type="error", content="Rate limited. Please try again shortly.")
        except litellm.APIError as exc:
            logger.warning("LLM API error: %s", exc)
            yield StreamEvent(type="error", content=f"API error: {str(exc)[:200]}")

    def _convert_tools(self, anthropic_tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI/LiteLLM tool format.

        Anthropic format:
          { "name": "...", "description": "...", "input_schema": { ... } }

        OpenAI/LiteLLM format:
          { "type": "function", "function": { "name": "...", "description": "...", "parameters": { ... } } }
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in anthropic_tools
        ]

    def _process_chunk(self, chunk) -> Optional[StreamEvent]:
        """Convert LiteLLM streaming chunk to StreamEvent."""
        delta = chunk.choices[0].delta if chunk.choices else None
        if not delta:
            return None

        # Text content
        if delta.content:
            return StreamEvent(type="text_delta", content=delta.content)

        # Tool calls (OpenAI format)
        if delta.tool_calls:
            tc = delta.tool_calls[0]
            if tc.function:
                if tc.function.name:
                    # Tool call start — accumulate
                    return None  # handled by accumulator pattern
                if tc.function.arguments:
                    return None  # accumulating JSON

        # Usage info (final chunk)
        if hasattr(chunk, 'usage') and chunk.usage:
            return StreamEvent(
                type="usage",
                input_tokens=chunk.usage.prompt_tokens or 0,
                output_tokens=chunk.usage.completion_tokens or 0,
            )

        return None

    async def close(self) -> None:
        """No persistent client to close with LiteLLM."""
        pass
```

### Tool Call Handling

LiteLLM returns tool calls in OpenAI format (chunked). Need a `_ToolAccumulator` similar to `claude.py` but for OpenAI streaming format:

```python
@dataclass
class _LiteLLMToolAccumulator:
    """Track streamed tool_call chunks (OpenAI format)."""
    id: str = ""
    name: str = ""
    arguments_json: str = ""

    def process_delta(self, tool_call_delta) -> Optional[StreamEvent]:
        if tool_call_delta.id:
            self.id = tool_call_delta.id
        if tool_call_delta.function:
            if tool_call_delta.function.name:
                self.name = tool_call_delta.function.name
            if tool_call_delta.function.arguments:
                self.arguments_json += tool_call_delta.function.arguments
        return None  # Accumulating

    def finish(self) -> StreamEvent:
        parsed = json.loads(self.arguments_json) if self.arguments_json else {}
        event = StreamEvent(
            type="tool_use",
            name=self.name,
            tool_input=parsed,
            tool_use_id=self.id,
        )
        self.reset()
        return event

    def reset(self) -> None:
        self.id = ""
        self.name = ""
        self.arguments_json = ""
```

---

## Chat WS Handler Changes

### Message Format (from frontend)

```json
{
  "type": "message",
  "content": "Plan my week",
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "api_key": "sk-ant-..."
}
```

All three fields optional — fallback to stored Anthropic key + default model.

### Router Changes (`chat.py`)

```python
async def _handle_message(ws, session_id, content, *, provider=None, api_key=None, model=None, ...):
    # Resolve LLM config
    if api_key and provider:
        # Frontend-provided key
        llm_config = LLMConfig(
            provider=provider,
            model=model or DEFAULT_MODELS.get(provider, "claude-sonnet-4-20250514"),
            api_key=api_key,
        )
        llm = LLMService(llm_config)
    else:
        # Fallback to stored Anthropic key
        key = get_api_key()
        if not key:
            await _send_event(ws, "error", content="API key not configured")
            return
        llm = ClaudeService(api_key=key)  # or LLMService with anthropic config

    # ... rest of handler uses llm.stream_response() ...
```

### Duel Changes (`council.py`)

`DuelOrchestrator.__init__` takes `LLMConfig` or `api_key` + `provider` + `model`:

```python
class DuelOrchestrator:
    def __init__(self, config: DuelConfig, llm_config: LLMConfig):
        self.config = config
        self.llm = LLMService(llm_config)
```

---

## System Prompt Adaptation

Different providers have different system prompt handling:

| Provider | System Prompt Approach |
|----------|----------------------|
| Anthropic | `system` parameter (native) — LiteLLM handles |
| OpenAI | First message with `role: "system"` — LiteLLM handles |
| Google | `system_instruction` — LiteLLM handles |

**LiteLLM normalizes this** — we pass `system` as a message and LiteLLM routes correctly. No manual adaptation needed.

---

## Token Tracking Updates

```python
# token_tracking.py — add provider to usage records

def record_usage(
    input_tokens: int,
    output_tokens: int,
    session_id: str = "",
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
) -> None:
    """Record usage with provider info for accurate cost estimation."""
    # Use litellm.model_cost for per-model pricing
    cost = litellm.completion_cost(
        model=model,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
    )
    # ... store in SQLite with provider + model columns ...
```

### SQLite Schema Addition

```sql
-- Add columns to usage table (migration)
ALTER TABLE token_usage ADD COLUMN provider TEXT DEFAULT 'anthropic';
ALTER TABLE token_usage ADD COLUMN model TEXT DEFAULT 'claude-sonnet-4-20250514';
```

---

## Installation

```bash
pip install litellm
```

Add to `requirements.txt`:
```
litellm>=1.40.0
```

> **Note**: LiteLLM is a pure Python package. It pulls in `openai` and `tiktoken`
> as dependencies. Total added: ~20MB.

---

## Error Mapping

| LiteLLM Exception | User Message |
|-------------------|-------------|
| `AuthenticationError` | "Invalid API key. Check your key in Settings." |
| `RateLimitError` | "Rate limited. Please try again shortly." |
| `NotFoundError` | "Model not available. Check provider/model in Settings." |
| `APIConnectionError` | "Cannot reach provider. Check your internet connection." |
| `Timeout` | "Request timed out. Please try again." |
| `APIError` (other) | "API error: {brief message}" |

---

## Acceptance Criteria

1. `LLMService` streams responses from Anthropic, OpenAI, Google AI
2. Chat WS handler accepts `provider` + `api_key` + `model` from message
3. Missing `api_key` falls back to stored Anthropic key
4. Tool calling works across all 3 providers
5. Token tracking records provider + model
6. Cost estimation uses LiteLLM's `model_cost`
7. Duel mode works with any configured provider
8. All existing Anthropic-only tests still pass
9. No API keys are logged or persisted by backend

---

## Tests

### Unit Tests (`test_llm_service.py`)
- Mock LiteLLM `acompletion` → verify StreamEvent conversion
- Tool format conversion (Anthropic → OpenAI format)
- Error handling (auth, rate limit, timeout)
- Model resolution (provider prefix mapping)

### Integration Tests (`test_chat_provider.py`)
- WS message with `provider` + `api_key` → uses LLMService
- WS message without `api_key` → falls back to stored key
- Invalid provider → error event
- Provider + wrong model → error event

### Migration Tests
- Existing tests with `ClaudeService` still pass
- Token tracking with provider column

---

## Rollback Plan

If LiteLLM proves problematic:
1. `ClaudeService` is not deleted — only its usage in `chat.py` is modified
2. Remove LiteLLM import, revert `chat.py` handler to direct `ClaudeService`
3. `LLMService` can stay as dead code until fixed

Keep `ClaudeService` intact until `LLMService` is proven stable for 1 week.
