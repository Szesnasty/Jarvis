"""Unified LLM service wrapping LiteLLM for multi-provider support.

Provides a streaming interface compatible with ClaudeService's StreamEvent
protocol, supporting Anthropic, OpenAI, and Google AI via LiteLLM.
"""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

import litellm

from services.claude import StreamEvent

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging
litellm.suppress_debug_info = True

# ── Config ───────────────────────────────────────────────────────────────────

PROVIDER_MODEL_MAP = {
    "anthropic": "",
    "openai": "",
    "google": "gemini/",
    "ollama": "",  # ollama_chat/ prefix already in litellm_model
}

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-2.5-flash",
    "ollama": "ollama_chat/qwen3:8b",
}

# All supported models per provider (for validation)
SUPPORTED_MODELS = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-haiku-4-20250514",
        "claude-opus-4-20250514",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
        "o3-mini",
    ],
    "google": [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
    "ollama": [],  # dynamic — any ollama_chat/ model accepted
}


# Per-provider timeout defaults (seconds)
PROVIDER_TIMEOUTS = {
    "anthropic": 120,
    "openai": 120,
    "google": 120,
    "ollama": 1800,  # local models can be slow on CPU/first load
}


@dataclass
class LLMConfig:
    """Per-request LLM configuration."""

    provider: str        # "anthropic" | "openai" | "google" | "ollama"
    model: str           # e.g. "claude-sonnet-4-20250514", "gpt-4o", "ollama_chat/qwen3:8b"
    api_key: str         # raw key from frontend, used once per request
    max_tokens: int = 4096
    temperature: float = 0.7
    api_base: Optional[str] = None   # e.g. "http://localhost:11434" for Ollama
    timeout: Optional[float] = None  # seconds; None = use PROVIDER_TIMEOUTS default


# ── Tool accumulator for OpenAI-format streamed tool_calls ───────────────────

@dataclass
class _LiteLLMToolAccumulator:
    """Track streamed tool_call chunks (OpenAI format).

    LiteLLM normalizes all providers to OpenAI-style delta.tool_calls.
    Each tool call arrives as incremental chunks with index, id, name, and
    partial arguments JSON.
    """

    calls: dict = field(default_factory=dict)  # index -> {id, name, arguments_json}

    def process_delta(self, tool_calls: list) -> None:
        """Accumulate tool call deltas."""
        for tc in tool_calls:
            idx = tc.index if hasattr(tc, "index") else 0
            if idx not in self.calls:
                self.calls[idx] = {"id": "", "name": "", "arguments_json": ""}
            entry = self.calls[idx]
            if tc.id:
                entry["id"] = tc.id
            if tc.function:
                if tc.function.name:
                    entry["name"] = tc.function.name
                if tc.function.arguments:
                    entry["arguments_json"] += tc.function.arguments

    def has_calls(self) -> bool:
        return bool(self.calls)

    def finish_all(self) -> list[StreamEvent]:
        """Produce StreamEvents for all accumulated tool calls."""
        events = []
        for _idx in sorted(self.calls):
            entry = self.calls[_idx]
            try:
                parsed = json.loads(entry["arguments_json"]) if entry["arguments_json"] else {}
            except json.JSONDecodeError:
                parsed = {}
            events.append(StreamEvent(
                type="tool_use",
                name=entry["name"],
                tool_input=parsed,
                tool_use_id=entry["id"],
            ))
        self.calls.clear()
        return events


# ── Tool format conversion ───────────────────────────────────────────────────

def convert_tools_anthropic_to_openai(anthropic_tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to OpenAI/LiteLLM tool format.

    Anthropic:
      { "name": "...", "description": "...", "input_schema": { ... } }

    OpenAI/LiteLLM:
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


def convert_tool_result_for_litellm(
    tool_use_id: str,
    tool_name: str,
    result: str,
) -> dict:
    """Build a tool result message in OpenAI format for LiteLLM.

    OpenAI format:
      { "role": "tool", "tool_call_id": "...", "content": "..." }
    """
    return {
        "role": "tool",
        "tool_call_id": tool_use_id,
        "content": result,
    }


def convert_messages_for_litellm(messages: list[dict]) -> list[dict]:
    """Convert Anthropic-style messages to OpenAI/LiteLLM format.

    Handles:
    - tool_use content blocks → assistant message with tool_calls
    - tool_result content blocks → tool role messages
    - plain text messages → pass through
    """
    converted = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        # Plain string content — pass through
        if isinstance(content, str):
            converted.append({"role": role, "content": content})
            continue

        # List of content blocks (Anthropic format)
        if isinstance(content, list):
            # Check what types of blocks we have
            block_types = {b.get("type") for b in content}

            # Tool use blocks → convert to assistant with tool_calls
            if "tool_use" in block_types and role == "assistant":
                tool_calls = []
                text_parts = []
                for block in content:
                    if block["type"] == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block.get("input", {})),
                            },
                        })
                    elif block["type"] == "text":
                        text_parts.append(block.get("text", ""))
                assistant_msg = {
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                    "tool_calls": tool_calls,
                }
                converted.append(assistant_msg)

            # Tool result blocks → convert to individual tool messages
            elif "tool_result" in block_types:
                for block in content:
                    if block["type"] == "tool_result":
                        converted.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", ""),
                        })

            # Other list content — join text blocks
            else:
                text = "\n".join(
                    b.get("text", "") for b in content if b.get("type") == "text"
                )
                converted.append({"role": role, "content": text or ""})
        else:
            converted.append({"role": role, "content": str(content) if content else ""})

    return converted


# ── LLM Service ──────────────────────────────────────────────────────────────

class LLMService:
    """Unified LLM service wrapping LiteLLM for multi-provider support.

    Yields the same StreamEvent objects as ClaudeService so the chat handler
    doesn't need to distinguish between providers.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._litellm_model = self._resolve_model()

    def _resolve_model(self) -> str:
        """Map provider + model to LiteLLM model string."""
        # Ollama models already include the ollama_chat/ prefix
        if self.config.provider == "ollama":
            model = self.config.model
            if not model.startswith("ollama"):
                model = f"ollama_chat/{model}"
            return model
        prefix = PROVIDER_MODEL_MAP.get(self.config.provider, "")
        return f"{prefix}{self.config.model}"

    async def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
    ) -> AsyncIterator[StreamEvent]:
        """Stream response — same interface as ClaudeService.stream_response."""
        try:
            # Convert Anthropic-style messages to OpenAI format for LiteLLM
            litellm_messages = [
                {"role": "system", "content": system_prompt},
            ] + convert_messages_for_litellm(messages)

            timeout = self.config.timeout or PROVIDER_TIMEOUTS.get(self.config.provider, 120)

            kwargs: dict[str, Any] = {
                "model": self._litellm_model,
                "messages": litellm_messages,
                "max_tokens": self.config.max_tokens,
                "stream": True,
                "api_key": self.config.api_key,
                "stream_options": {"include_usage": True},
                "timeout": timeout,
            }

            if self.config.api_base:
                kwargs["api_base"] = self.config.api_base

            if tools:
                kwargs["tools"] = convert_tools_anthropic_to_openai(tools)

            response = await litellm.acompletion(**kwargs)

            tool_acc = _LiteLLMToolAccumulator()

            async for chunk in response:
                # Some chunks don't have choices (e.g. final usage-only chunk)
                if not chunk.choices:
                    # Check for usage in final chunk
                    usage = getattr(chunk, "usage", None)
                    if usage:
                        yield StreamEvent(
                            type="usage",
                            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                        )
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Text content
                if delta and delta.content:
                    yield StreamEvent(type="text_delta", content=delta.content)

                # Tool calls (streamed in chunks)
                if delta and delta.tool_calls:
                    tool_acc.process_delta(delta.tool_calls)

                # When the generation finishes with tool calls, emit them
                if finish_reason == "tool_calls" or (finish_reason == "stop" and tool_acc.has_calls()):
                    for tool_event in tool_acc.finish_all():
                        yield tool_event

                # Usage in chunk (some providers include it)
                usage = getattr(chunk, "usage", None)
                if usage and (getattr(usage, "prompt_tokens", None) or getattr(usage, "completion_tokens", None)):
                    yield StreamEvent(
                        type="usage",
                        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    )

            # Flush any remaining tool calls
            if tool_acc.has_calls():
                for tool_event in tool_acc.finish_all():
                    yield tool_event

            yield StreamEvent(type="done")

        except litellm.AuthenticationError:
            yield StreamEvent(
                type="error",
                content="Invalid API key. Check your key in Settings.",
            )
        except litellm.RateLimitError:
            yield StreamEvent(
                type="error",
                content="Rate limited. Please try again shortly.",
            )
        except litellm.NotFoundError:
            yield StreamEvent(
                type="error",
                content="Model not available. Check provider/model in Settings.",
            )
        except litellm.APIConnectionError:
            yield StreamEvent(
                type="error",
                content="Cannot reach provider. Check your internet connection.",
            )
        except litellm.Timeout:
            yield StreamEvent(
                type="error",
                content="Request timed out. Please try again.",
            )
        except litellm.APIError as exc:
            logger.warning("LLM API error: %s", exc)
            yield StreamEvent(
                type="error",
                content=f"API error: {str(exc)[:200]}",
            )
        except Exception as exc:
            logger.exception("Unexpected LLM error")
            yield StreamEvent(
                type="error",
                content=f"Unexpected error: {str(exc)[:200]}",
            )

    async def close(self) -> None:
        """No persistent client to close with LiteLLM."""
        pass
