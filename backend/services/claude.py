import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

from services.context_builder import build_context

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are Jarvis, a personal memory and planning assistant.

You work on the user's local knowledge base — Markdown files organized in folders.
The user's memory belongs to them. You help organize, search, plan, and connect their notes.

Rules:
- Be concise and direct
- Use the user's own notes as primary source
- When you create or modify notes, use Markdown with YAML frontmatter
- If you don't know something, say so — don't invent information
- When relevant, suggest saving important information to memory

You have access to the following tools to work with the user's memory."""


@dataclass
class StreamEvent:
    type: str  # "text_delta" | "tool_use" | "tool_result" | "done" | "error" | "usage"
    content: str = ""
    name: str = ""
    tool_input: Optional[dict[str, Any]] = None
    tool_use_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class _ToolAccumulator:
    """Tracks in-progress tool_use block while streaming."""

    name: str = ""
    input_json: str = ""
    use_id: str = ""

    def start(self, name: str, use_id: str) -> None:
        self.name = name
        self.use_id = use_id
        self.input_json = ""

    def is_active(self) -> bool:
        return bool(self.name)

    def finish(self) -> StreamEvent:
        try:
            parsed = json.loads(self.input_json) if self.input_json else {}
        except json.JSONDecodeError:
            parsed = {}
        event = StreamEvent(
            type="tool_use",
            name=self.name,
            tool_input=parsed,
            tool_use_id=self.use_id,
        )
        self.name = ""
        self.input_json = ""
        self.use_id = ""
        return event


def _handle_block_start(event, tool: _ToolAccumulator) -> None:
    if event.content_block.type != "tool_use":
        return
    tool.start(event.content_block.name, event.content_block.id)


def _handle_block_delta(event, tool: _ToolAccumulator) -> Optional[StreamEvent]:
    if event.delta.type == "text_delta":
        return StreamEvent(type="text_delta", content=event.delta.text)
    if event.delta.type == "input_json_delta":
        tool.input_json += event.delta.partial_json
    return None


def _handle_block_stop(tool: _ToolAccumulator) -> Optional[StreamEvent]:
    if not tool.is_active():
        return None
    return tool.finish()


class ClaudeService:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def close(self) -> None:
        """Close the underlying HTTP client to release connections."""
        await self.client.close()

    async def stream_response(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
    ) -> AsyncIterator[StreamEvent]:
        """Yields streaming events from Claude."""
        try:
            async for stream_event in self._iter_stream(messages, system_prompt, tools):
                yield stream_event
        except anthropic.RateLimitError:
            yield StreamEvent(
                type="error",
                content="Rate limited by Claude API. Please try again shortly.",
            )
        except anthropic.APIStatusError as exc:
            if exc.status_code == 529 or "overloaded" in str(exc).lower():
                msg = "Claude is currently overloaded. Please try again in a moment."
            elif exc.status_code == 401:
                msg = "Invalid API key. Please check your key in Settings."
            elif exc.status_code == 403:
                msg = "API key does not have permission for this model."
            elif exc.status_code >= 500:
                msg = "Claude API is experiencing issues. Please try again shortly."
            else:
                msg = f"Claude API error ({exc.status_code}). Please try again."
            logger.warning("Claude API error %d: %s", exc.status_code, exc)
            yield StreamEvent(type="error", content=msg)
        except anthropic.APIError as exc:
            logger.warning("Claude API error: %s", exc)
            yield StreamEvent(type="error", content="Failed to reach Claude API. Please try again.")

    async def _iter_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict],
    ) -> AsyncIterator[StreamEvent]:
        tool = _ToolAccumulator()

        async with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
            tools=tools,
        ) as stream:
            async for event in stream:
                result = self._process_event(event, tool)
                if result is not None:
                    yield result

    def _process_event(self, event, tool: _ToolAccumulator) -> Optional[StreamEvent]:
        if event.type == "content_block_start":
            _handle_block_start(event, tool)
            return None
        if event.type == "content_block_delta":
            return _handle_block_delta(event, tool)
        if event.type == "content_block_stop":
            return _handle_block_stop(tool)
        if event.type == "message_delta":
            # Capture usage from the final message event
            usage = getattr(event, "usage", None)
            if usage:
                return StreamEvent(
                    type="usage",
                    input_tokens=getattr(usage, "input_tokens", 0),
                    output_tokens=getattr(usage, "output_tokens", 0),
                )
        if event.type == "message_start":
            msg = getattr(event, "message", None)
            if msg:
                usage = getattr(msg, "usage", None)
                if usage:
                    return StreamEvent(
                        type="usage",
                        input_tokens=getattr(usage, "input_tokens", 0),
                        output_tokens=getattr(usage, "output_tokens", 0),
                    )
        return None


async def build_system_prompt(
    user_message: str,
    workspace_path=None,
) -> str:
    """Build system prompt with optional context and active specialist."""
    from services import specialist_service

    base = SYSTEM_PROMPT
    active = specialist_service.get_active_specialist()
    if active:
        base = specialist_service.build_specialist_prompt(active, base)

    context = await build_context(user_message, workspace_path=workspace_path)
    if not context:
        return base
    return (
        base
        + "\n\nHere are potentially relevant notes from the user's memory:\n"
        + context
    )
