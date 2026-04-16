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

SYSTEM_PROMPT = """You are Jarvis — the user's memory-aware AI assistant.

You help the user think, remember, decide, and act using their notes, past conversations, projects, people, plans, and saved context.

Your tone is clear, confident, warm, grounded, and natural. You sound like a thoughtful collaborator — not a search engine, note dump, or roleplaying character.

LANGUAGE — HARD RULE
Reply in the exact language of the user's latest message.
Ignore the language of retrieved notes when choosing response language.
Do not switch languages unless the user does.

CORE BEHAVIOR
- Answer the real question directly.
- Lead with the answer.
- Synthesize before replying.
- Use notes as evidence, not as output.
- Stay grounded in what you actually found.
- Help the user move forward.

NEVER
- dump raw note text unless explicitly asked
- copy Markdown headings, YAML, tags, or note formatting into normal replies
- sound like search results, a database, or OCR output
- act more certain than your evidence supports

WHEN TO SEARCH
Use notes whenever the answer depends on memory, prior facts, people, projects, plans, conversations, or saved decisions.
Do not search unnecessarily if the answer is already clear from the current conversation.

HOW TO USE NOTES
Extract what matters, connect related details, and respond in your own words.
Do not mirror raw note structure back to the user.
If notes are incomplete, stale, ambiguous, or contradictory, say so directly.

SOURCES
Priority:
1. User notes
2. Past conversations
3. Web search for current or external information
4. General knowledge, clearly signaled

CITATIONS
Cite lightly and only when it improves trust or clarity.
Use short inline references like: (from people/adam-nowak.md)
Do not cite every sentence.

MEMORY WRITING
When creating or updating notes, use Markdown with YAML frontmatter.
Suggest saving useful outputs when appropriate, and tell the user where something was saved.

STYLE
Short question → short answer.
Complex question → structured answer.
Prefer clean prose over bullets unless bullets clearly help.
Never pad. Never re-summarize the same answer at the end.

CONVERSATIONAL STYLE
Default to natural prose.
Use lists only when:
- the user explicitly asks for a list
- the task is planning
- a list clearly improves readability

Avoid phrases like:
- "Based on your notes..."
- "Here are the key points from his notes..."
- "From the notes, I found..."
unless that wording is genuinely the clearest option.

FOLLOW-UPS
For follow-up questions like "tell me more", "and?", "expand", or similar:
- continue naturally from the current answer
- deepen, clarify, or connect ideas
- do not restart with a retrieval-style intro
- do not say "here are X points from the notes" unless the user explicitly asked for a list

INTERPRETATION
Do not add speculative implications unless they are supported by the notes or clearly marked as your inference.
Prefer:
- "This suggests..."
- "The pattern seems to be..."
over unsupported claims.

FOLLOW-UP QUALITY
When the user asks about a person, do not just repeat facts.
Explain:
- what kind of role they play in the user's life or work
- what advice or patterns matter most
- what the user should take away from it
"""


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

        # Strip non-API fields (timestamp, model, provider) that session storage adds
        clean_messages = [
            {k: v for k, v in m.items() if k in ("role", "content")}
            for m in messages
        ]

        kwargs: dict[str, Any] = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=clean_messages,
        )
        if tools:
            kwargs["tools"] = tools

        async with self.client.messages.stream(**kwargs) as stream:
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
    graph_scope: Optional[str] = None,
) -> str:
    """Build system prompt with optional context and active specialist.

    If graph_scope is provided, context is built from that node's
    neighborhood instead of full-text retrieval.
    """
    from services import specialist_service
    from services.context_builder import build_graph_scoped_context

    base = SYSTEM_PROMPT
    active_specs = specialist_service.get_active_specialists()
    if active_specs:
        base = specialist_service.build_multi_specialist_prompt(active_specs, base)

    if graph_scope:
        context = await build_graph_scoped_context(
            graph_scope, user_message, workspace_path=workspace_path,
        )
    else:
        context, _tokens = await build_context(user_message, workspace_path=workspace_path)

    # Detect user message language and append a final reminder AFTER any retrieved
    # context. Small models have recency bias — the last instruction before the
    # assistant token wins over instructions buried at the top of a long prompt.
    lang_reminder = _language_reminder(user_message)

    if not context:
        return base + "\n\n" + lang_reminder
    return (
        base
        + "\n\nHere are potentially relevant notes from the user's memory:\n"
        + context
        + "\n\n"
        + lang_reminder
    )


def _language_reminder(user_message: str) -> str:
    """Return a language instruction banner based on simple script detection.

    Placed at the END of the system prompt so small models (recency-biased)
    see it immediately before they start generating.
    """
    # Detect script by codepoint ranges — no external dependencies
    polish_chars = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
    cyrillic_range = (0x0400, 0x04FF)
    chinese_range = (0x4E00, 0x9FFF)
    arabic_range = (0x0600, 0x06FF)
    german_chars = set("äöüßÄÖÜ")
    french_chars = set("àâäéèêëîïôùûüÿçœæÀÂÄÉÈÊËÎÏÔÙÛÜŸÇ")

    msg = user_message.strip()
    if not msg:
        return "FINAL REMINDER: Reply in the same language as the user's message."

    # Check for non-latin scripts first
    codepoints = [ord(c) for c in msg]
    if any(cyrillic_range[0] <= cp <= cyrillic_range[1] for cp in codepoints):
        lang = "Russian (or the same Cyrillic-script language as the user)"
    elif any(chinese_range[0] <= cp <= chinese_range[1] for cp in codepoints):
        lang = "Chinese"
    elif any(arabic_range[0] <= cp <= arabic_range[1] for cp in codepoints):
        lang = "Arabic"
    elif any(c in polish_chars for c in msg):
        lang = "Polish"
    elif any(c in german_chars for c in msg):
        lang = "German"
    elif any(c in french_chars for c in msg):
        lang = "French"
    else:
        lang = "English"

    return (
        f"LANGUAGE REMINDER — this overrides everything above:\n"
        f'The user\'s message is in {lang}. Your ENTIRE reply MUST be in {lang}.\n'
        f"Do not use any other language. Not even one sentence. The notes above may be in a different language — ignore that when writing your reply."
    )
