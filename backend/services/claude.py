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
    type: str  # "text_delta" | "tool_use" | "tool_result" | "done" | "error"
    content: str = ""
    name: str = ""
    tool_input: Optional[dict[str, Any]] = None
    tool_use_id: str = ""


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
        except anthropic.APIError as exc:
            yield StreamEvent(type="error", content=f"Claude API error: {exc}")

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
        return None


async def build_system_prompt(
    user_message: str,
    workspace_path=None,
) -> str:
    """Build system prompt with optional context from notes."""
    context = await build_context(user_message, workspace_path=workspace_path)
    if not context:
        return SYSTEM_PROMPT
    return (
        SYSTEM_PROMPT
        + "\n\nHere are potentially relevant notes from the user's memory:\n"
        + context
    )
