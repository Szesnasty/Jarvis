"""Step 30b — rolling conversation summary.

As a chat grows past ``RECENT_WINDOW`` messages, older turns are folded
into a compact textual summary which is injected at the top of the
system prompt. This keeps the prompt cost flat after the window fills
while preserving topical memory ("you mentioned X earlier, then we
decided Y").

The summariser uses whichever provider/model the chat itself is using
so a local-only user does not suddenly hit the cloud.

Failure mode: any error inside ``fold_messages_into_summary`` is logged
and the existing summary is returned unchanged. The chat reply is never
blocked or delayed by summarisation — the fold runs asynchronously
*after* the assistant reply has been streamed back to the user.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Tunables ──────────────────────────────────────────────────────────────────
RECENT_WINDOW = 16          # messages kept verbatim in the LLM prompt
SUMMARY_BUDGET_TOKENS = 600  # hard cap for the rolling summary
SUMMARY_BUDGET_CHARS = SUMMARY_BUDGET_TOKENS * 4
FOLD_BATCH = 4              # messages folded per turn once the window overflows
SUMMARY_TIMEOUT_S = 8.0     # never block the chat for longer than this


SUMMARY_SYSTEM_PROMPT = """You maintain a rolling summary of a long conversation between a user and Jarvis (their AI assistant).

You receive the CURRENT SUMMARY plus a few NEW MESSAGES that have just rolled out of the recent window. Output ONLY the updated summary — no preface, no explanation, no greeting.

Rules:
- Write in the user's language (match the existing summary's language; if the summary is empty, match the new messages).
- Bullet form, at most 10 bullets total.
- Preserve concrete facts: names, decisions, dates, file paths, unresolved questions, conclusions.
- Drop chit-chat, acknowledgements, tool mechanics, "I'll search now" filler.
- Stay under {budget} tokens. If the input would push you over the budget, drop the oldest / lowest-signal bullets first.
"""


def _format_messages_block(messages: list[dict]) -> str:
    """Render the new-messages block fed to the summariser."""
    parts: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            # Tool-use / tool-result blocks — collapse to a hint, not the payload.
            block_types = {b.get("type") for b in content if isinstance(b, dict)}
            if "tool_use" in block_types:
                names = sorted({
                    b.get("name", "tool") for b in content
                    if isinstance(b, dict) and b.get("type") == "tool_use"
                })
                parts.append(f"[{role}] (called tools: {', '.join(names)})")
                continue
            if "tool_result" in block_types:
                parts.append(f"[{role}] (tool result received)")
                continue
            # Mixed text-only list
            text = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
            content = text
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        if not content:
            continue
        # Cap each message we feed the summariser so a single huge paste
        # doesn't blow the input.
        if len(content) > 1500:
            content = content[:1500] + " …"
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def mechanical_summary(
    existing_summary: str,
    new_messages: list[dict],
    *,
    budget_chars: int = SUMMARY_BUDGET_CHARS,
) -> str:
    """Cheap, deterministic fallback used when no LLM call is allowed.

    Keeps a chronological list of short ``User asked: …`` / ``Jarvis: …``
    lines truncated to 120 chars each, capped at 10 entries. No
    interpretation, but topics survive.
    """
    lines: list[str] = []
    if existing_summary:
        # Preserve prior bullets so the chronology is stable.
        for ln in existing_summary.splitlines():
            ln = ln.rstrip()
            if ln:
                lines.append(ln)
    for m in new_messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if isinstance(content, list):
            continue  # skip tool blocks in mechanical mode
        if not isinstance(content, str):
            content = str(content)
        content = content.strip().replace("\n", " ")
        if not content:
            continue
        label = "User asked" if role == "user" else "Jarvis"
        snippet = content[:120] + (" …" if len(content) > 120 else "")
        lines.append(f"- {label}: {snippet}")
    # Tail-truncate to 10 entries, then hard-cap chars.
    if len(lines) > 10:
        lines = lines[-10:]
    out = "\n".join(lines)
    if len(out) > budget_chars:
        out = out[-budget_chars:]
        # Re-trim to start at a bullet boundary.
        nl = out.find("\n- ")
        if nl >= 0:
            out = out[nl + 1:]
    return out


async def _llm_fold(
    existing_summary: str,
    new_messages: list[dict],
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: Optional[str] = None,
    budget_tokens: int = SUMMARY_BUDGET_TOKENS,
) -> str:
    """Call the chat provider to fold ``new_messages`` into ``existing_summary``.

    Imports are local so this module stays import-cheap.
    """
    from services.claude import ClaudeService
    from services.llm_service import LLMConfig, LLMService, DEFAULT_MODELS

    system = SUMMARY_SYSTEM_PROMPT.format(budget=budget_tokens)
    user_block = (
        f"CURRENT SUMMARY:\n{existing_summary or '(empty)'}\n\n"
        f"NEW MESSAGES TO FOLD IN:\n{_format_messages_block(new_messages)}\n\n"
        f"Return the updated summary only."
    )
    messages = [{"role": "user", "content": user_block}]

    # Build an LLM client matching the active chat provider.
    if provider == "ollama":
        from services.ollama_service import DEFAULT_OLLAMA_BASE_URL
        client = LLMService(LLMConfig(
            provider="ollama",
            model=model or DEFAULT_MODELS.get("ollama", "ollama_chat/qwen3:8b"),
            api_key="ollama",
            api_base=base_url or DEFAULT_OLLAMA_BASE_URL,
            timeout=int(SUMMARY_TIMEOUT_S),
        ))
    elif provider and provider != "anthropic":
        client = LLMService(LLMConfig(
            provider=provider,
            model=model or DEFAULT_MODELS.get(provider, "gpt-4o"),
            api_key=api_key,
        ))
    else:
        client = ClaudeService(api_key=api_key)

    try:
        out_parts: list[str] = []
        async for event in client.stream_response(
            messages=messages,
            system_prompt=system,
            tools=[],
        ):
            if event.type == "text_delta" and event.content:
                out_parts.append(event.content)
        text = "".join(out_parts).strip()
    finally:
        try:
            await client.close()
        except Exception:
            pass

    if not text:
        return existing_summary
    if len(text) > SUMMARY_BUDGET_CHARS:
        # Hard cap so a runaway summary never grows unbounded.
        text = text[:SUMMARY_BUDGET_CHARS].rsplit("\n", 1)[0]
    return text


async def fold_messages_into_summary(
    existing_summary: str,
    new_messages: list[dict],
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: Optional[str] = None,
    use_llm: bool = True,
) -> str:
    """Public entry point. Always returns a usable summary string.

    Never raises — on any error or timeout, returns ``existing_summary``
    unchanged. Honours ``SUMMARY_TIMEOUT_S``.
    """
    if not new_messages:
        return existing_summary

    if not use_llm or provider == "ollama" or not api_key:
        # Mechanical fallback for offline / local-only users.
        return mechanical_summary(existing_summary, new_messages)

    try:
        return await asyncio.wait_for(
            _llm_fold(
                existing_summary,
                new_messages,
                provider=provider,
                model=model,
                api_key=api_key,
                base_url=base_url,
            ),
            timeout=SUMMARY_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("Conversation summary fold timed out — keeping previous summary")
    except Exception:
        logger.warning("Conversation summary fold failed — keeping previous summary", exc_info=True)
    return existing_summary
