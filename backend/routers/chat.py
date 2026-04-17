import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import session_service
from services import specialist_service
from services.claude import ClaudeService, StreamEvent, build_system_prompt
from services.llm_service import LLMConfig, LLMService, DEFAULT_MODELS
from services.tools import TOOLS, ToolNotFoundError, execute_tool
from services.token_tracking import check_budget, log_usage
from services.workspace_service import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _send_event(ws: WebSocket, event_type: str, **fields) -> None:
    await ws.send_json({"type": event_type, **fields})


async def _run_tool(event: StreamEvent, session_id: str = "", api_key: str = "") -> str:
    try:
        return await execute_tool(
            event.name,
            event.tool_input or {},
            session_id=session_id,
            api_key=api_key or None,
        )
    except ToolNotFoundError:
        return f"Unknown tool: {event.name}"
    except Exception as exc:
        return f"Tool error: {exc}"


_MEMORY_MUTATING_TOOLS = frozenset({"write_note", "append_note", "create_plan", "update_plan"})

# Debounce background session saves: track pending save tasks per session
# so we cancel the previous scheduled save when a new reply arrives.
_pending_saves: dict[str, asyncio.Task] = {}


async def _save_session_bg(session_id: str) -> None:
    """Background task: save session to memory note + update graph.

    Debounced: waits 2 seconds so rapid-fire replies don't cause
    concurrent SQLite writes. Only the last scheduled save actually runs.
    """
    try:
        await asyncio.sleep(2)
        await session_service.save_session_to_memory(session_id)
    except asyncio.CancelledError:
        pass  # Expected when a newer save supersedes this one
    except Exception:
        logger.warning("Background save_session_to_memory failed for %s", session_id)
    finally:
        _pending_saves.pop(session_id, None)


def _schedule_session_save(session_id: str) -> None:
    """Schedule a debounced background save, cancelling any pending one."""
    old_task = _pending_saves.pop(session_id, None)
    if old_task and not old_task.done():
        old_task.cancel()
    _pending_saves[session_id] = asyncio.ensure_future(_save_session_bg(session_id))


async def _emit_memory_changed(ws: WebSocket, tool_name: str, tool_input: dict) -> None:
    """Emit memory_changed event for tools that modify notes."""
    if tool_name in _MEMORY_MUTATING_TOOLS:
        path = tool_input.get("path", "")
        await _send_event(ws, "memory_changed", path=path, action=tool_name)


def _build_tool_messages(
    messages: list[dict],
    event: StreamEvent,
    result: str,
) -> list[dict]:
    return messages + [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": event.tool_use_id,
                    "name": event.name,
                    "input": event.tool_input or {},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": event.tool_use_id,
                    "content": result,
                }
            ],
        },
    ]


MAX_TOOL_ROUNDS = 5


async def _stream_follow_up(
    ws: WebSocket,
    claude,  # ClaudeService | LLMService
    tool_messages: list[dict],
    system_prompt: str,
    tools: list[dict],
    session_id: str,
    api_key: str,
    usage_acc: list[int],
    depth: int = 1,
) -> str:
    """Stream Claude's follow-up after tool execution.

    Supports recursive tool calls up to MAX_TOOL_ROUNDS total.
    Returns accumulated text.
    """
    text = ""
    pending_tools: list[StreamEvent] = []

    async for event in claude.stream_response(
        messages=tool_messages,
        system_prompt=system_prompt,
        tools=tools,
    ):
        if event.type == "text_delta":
            text += event.content
            await _send_event(ws, "text_delta", content=event.content)
        elif event.type == "tool_use":
            pending_tools.append(event)
        elif event.type == "usage":
            usage_acc[0] += event.input_tokens
            usage_acc[1] += event.output_tokens
        elif event.type == "error":
            await _send_event(ws, "error", content=event.content)

    # If Claude wants tool calls, execute them and recurse
    if pending_tools and depth < MAX_TOOL_ROUNDS:
        next_messages = tool_messages
        for tool_event in pending_tools:
            await _send_event(ws, "tool_use", name=tool_event.name, input=tool_event.tool_input)
            session_service.record_tool_use(session_id, tool_event.name)
            result = await _run_tool(tool_event, session_id=session_id, api_key=api_key)
            await _send_event(ws, "tool_result", name=tool_event.name, content=result)
            await _emit_memory_changed(ws, tool_event.name, tool_event.tool_input or {})
            next_messages = _build_tool_messages(next_messages, tool_event, result)

        text += await _stream_follow_up(
            ws, claude, next_messages, system_prompt, tools,
            session_id, api_key, usage_acc, depth + 1,
        )

    return text


def _make_llm(provider: Optional[str], model: Optional[str], api_key: str, base_url: Optional[str] = None):
    """Create an LLMService for the given provider, or ClaudeService as fallback."""
    if provider == "ollama":
        from services.ollama_service import DEFAULT_OLLAMA_BASE_URL
        config = LLMConfig(
            provider="ollama",
            model=model or DEFAULT_MODELS.get("ollama", "ollama_chat/qwen3:8b"),
            api_key="ollama",  # LiteLLM needs a non-empty string
            api_base=base_url or DEFAULT_OLLAMA_BASE_URL,
            timeout=1800,
        )
        return LLMService(config)
    if provider and provider != "anthropic":
        config = LLMConfig(
            provider=provider,
            model=model or DEFAULT_MODELS.get(provider, "gpt-4o"),
            api_key=api_key,
        )
        return LLMService(config)
    # Anthropic — use native ClaudeService for best streaming fidelity
    return ClaudeService(api_key=api_key)


async def _handle_message(
    ws: WebSocket,
    session_id: str,
    content: str,
    get_llm: callable = None,
    graph_scope: Optional[str] = None,
    client_api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> None:
    api_key = client_api_key or get_api_key()
    if not api_key and provider != "ollama":
        await _send_event(ws, "error", content="API key not configured")
        return

    session_service.add_message(session_id, "user", content)
    messages = session_service.get_messages(session_id)
    system_prompt = await build_system_prompt(content, graph_scope=graph_scope)
    active_specs = specialist_service.get_active_specialists()
    tools = specialist_service.filter_tools(TOOLS, specialists=active_specs)
    # Check token budget before calling Claude
    budget = check_budget()
    if budget["level"] == "exceeded":
        await _send_event(ws, "error", content=f"Daily token budget exceeded ({budget['percent']:.0f}% used). Please try again tomorrow or increase your budget.")
        await _send_event(ws, "done", session_id=session_id)
        return
    if budget["level"] == "warning":
        await _send_event(ws, "warning", content=f"Approaching daily token budget ({budget['percent']:.0f}% used).")

    claude = get_llm(api_key or "", provider, model, base_url) if get_llm else _make_llm(provider, model, api_key or "", base_url)
    assistant_text = ""
    # Specialist attribution: prefix first text_delta with specialist names
    attribution_prefix = ""
    if active_specs:
        names = ", ".join(s["name"] for s in active_specs)
        attribution_prefix = f"**[{names}]** "
    # [input_tokens, output_tokens] accumulated across all rounds
    usage_acc = [0, 0]
    pending_tools: list[StreamEvent] = []

    async for event in claude.stream_response(
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
    ):
        if event.type == "text_delta":
            content = event.content
            if attribution_prefix:
                content = attribution_prefix + content
                attribution_prefix = ""  # Only prepend once
            assistant_text += content
            await _send_event(ws, "text_delta", content=content)

        elif event.type == "tool_use":
            pending_tools.append(event)

        elif event.type == "usage":
            usage_acc[0] += event.input_tokens
            usage_acc[1] += event.output_tokens

        elif event.type == "error":
            await _send_event(ws, "error", content=event.content)

    # Handle tool call chain (up to MAX_TOOL_ROUNDS)
    if pending_tools:
        tool_messages = messages
        for tool_event in pending_tools:
            await _send_event(ws, "tool_use", name=tool_event.name, input=tool_event.tool_input)
            session_service.record_tool_use(session_id, tool_event.name)
            result = await _run_tool(tool_event, session_id=session_id, api_key=api_key)
            await _send_event(ws, "tool_result", name=tool_event.name, content=result)
            await _emit_memory_changed(ws, tool_event.name, tool_event.tool_input or {})
            tool_messages = _build_tool_messages(tool_messages, tool_event, result)

        assistant_text += await _stream_follow_up(
            ws, claude, tool_messages, system_prompt, tools,
            session_id, api_key, usage_acc,
        )

    if assistant_text:
        session_service.add_message(
            session_id, "assistant", assistant_text,
            model=model or "claude-sonnet-4-20250514",
            provider=provider or "anthropic",
        )
    else:
        # No text response (e.g. pure tool-use) — still persist so session
        # state stays consistent, but add_message already auto-saves on the
        # user message so an extra save here is only needed when we have text.
        pass

    # Log token usage if we got any
    if usage_acc[0] > 0 or usage_acc[1] > 0:
        try:
            log_usage(
                usage_acc[0], usage_acc[1],
                model=model or "claude-sonnet-4-20250514",
                provider=provider or "anthropic",
            )
        except Exception:
            logger.warning("Failed to log token usage")

    done_fields = {
        "session_id": session_id,
        "model": model or "claude-sonnet-4-20250514",
        "provider": provider or "anthropic",
    }
    # Include tool_mode for local models so the frontend can show tool support info
    if provider == "ollama" and model:
        from services.ollama_service import MODEL_CATALOG, _tool_mode_for
        ollama_name = model.replace("ollama_chat/", "") if model.startswith("ollama_chat/") else model
        for entry in MODEL_CATALOG:
            if entry.ollama_model == ollama_name:
                done_fields["tool_mode"] = _tool_mode_for(entry)
                break
        else:
            done_fields["tool_mode"] = "json_fallback"

    await _send_event(ws, "done", **done_fields)

    # Save conversation to memory after every assistant reply.
    # First save happens after the first exchange; subsequent saves update the
    # same note (dedup by session_id in frontmatter).
    _schedule_session_save(session_id)


def _parse_message(raw: str) -> tuple:
    """Parse raw WS text. Returns (data, error_message).
    Returns (None, None) for control messages like ping that should be silently ignored.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "Invalid JSON"

    # Silently ignore heartbeat pings
    if data.get("type") == "ping":
        return None, None

    # Duel start messages have their own validation
    if data.get("type") == "duel_start":
        return data, None

    content = data.get("content", "").strip()
    if not content:
        return None, "Message content is required"

    return data, None


async def _handle_duel(
    ws: WebSocket,
    data: dict,
    session_id: str,
    get_llm: callable,
    client_api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Handle a duel_start WS message."""
    from services.council import DuelConfig, DuelOrchestrator, validate_duel_config

    api_key = client_api_key or get_api_key()
    if not api_key:
        await _send_event(ws, "error", content="API key not configured")
        return

    topic = data.get("topic", "").strip()
    specialist_ids = data.get("specialist_ids", [])

    config = DuelConfig(topic=topic, specialist_ids=specialist_ids)
    try:
        validate_duel_config(config)
    except ValueError as exc:
        await _send_event(ws, "error", content=str(exc))
        return

    claude = get_llm(api_key, provider, model)
    orchestrator = DuelOrchestrator(claude)

    try:
        async for event in orchestrator.run(config):
            # Map DuelEvent to WS JSON
            ws_data = {"type": f"duel_{event.type}"}
            if event.specialist:
                ws_data["specialist"] = event.specialist
            if event.content:
                ws_data["content"] = event.content
            if event.round_num:
                ws_data["round"] = event.round_num
            if event.metadata:
                ws_data.update(event.metadata)
            await ws.send_json(ws_data)

            # If duel finished, add verdict summary to session for continued chat
            if event.type == "judge_done":
                summary = (
                    f"**Duel Verdict — {topic}**\n\n"
                    f"Winner: {event.metadata.get('winner', '?')}\n\n"
                    f"{event.metadata.get('reasoning', '')}\n\n"
                    f"{event.metadata.get('recommendation', '')}"
                )
                session_service.add_message(session_id, "assistant", summary)
    except Exception as exc:
        logger.exception("Duel error")
        await _send_event(ws, "duel_error", content=f"Duel failed: {exc}")


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    # Origin allowlist check — CORSMiddleware does not cover WebSocket
    # handshakes, so enforce it manually to prevent cross-site WS hijacking.
    from config import get_settings as _get_settings
    origin = websocket.headers.get("origin")
    allowed_origins = _get_settings().cors_origins
    if origin is not None and origin not in allowed_origins:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    # Allow resuming an existing session via query param (e.g. after reconnect)
    resume_id = websocket.query_params.get("session_id", "").strip()
    # Validate format before any lookup to prevent abuse
    _valid_resume = bool(resume_id and session_service.is_valid_session_id(resume_id))
    if _valid_resume and session_service.get_session(resume_id):
        # Session still in memory — just reattach
        session_id = resume_id
    elif _valid_resume:
        # Session was saved to disk but cleared from memory — try to reload
        try:
            session_id = session_service.resume_session(resume_id)
        except Exception:
            session_id = session_service.create_session()
    else:
        session_id = session_service.create_session()

    await _send_event(websocket, "session_start", session_id=session_id)

    # Send existing messages so the frontend can restore chat history after refresh
    existing = session_service.get_messages(session_id)
    if existing:
        await _send_event(websocket, "session_history", messages=existing)

    # Reuse a single LLM service per connection to avoid per-message HTTP pool churn.
    # Cache is keyed on (api_key, provider, model) — changed key/provider creates new instance.
    _connection_llm = None
    _connection_llm_key: tuple = (None, None, None, None)  # (api_key, provider, model, base_url)

    def _get_llm(api_key: str, provider: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        nonlocal _connection_llm, _connection_llm_key
        cache_key = (api_key, provider, model, base_url)
        if _connection_llm is None or _connection_llm_key != cache_key:
            _connection_llm = _make_llm(provider, model, api_key, base_url)
            _connection_llm_key = cache_key
        return _connection_llm

    try:
        while True:
            raw = await websocket.receive_text()
            data, error = _parse_message(raw)

            # Silently ignore pings (data=None, error=None)
            if data is None and error is None:
                continue

            if error:
                await _send_event(websocket, "error", content=error)
                continue

            # Extract client-provided API key + provider + model (browser-only storage)
            client_api_key = data.get("api_key") or None
            client_provider = data.get("provider") or None
            client_model = data.get("model") or None
            client_base_url = data.get("base_url") or None

            # Route duel messages
            if data.get("type") == "duel_start":
                await _handle_duel(
                    websocket, data, session_id, _get_llm,
                    client_api_key=client_api_key,
                    provider=client_provider, model=client_model,
                )
                continue

            content = data.get("content", "").strip()

            requested_sid = data.get("session_id")
            if requested_sid and requested_sid != session_id:
                if session_service.get_session(requested_sid):
                    session_id = requested_sid

            graph_scope = data.get("graph_scope") or None
            await _handle_message(
                websocket, session_id, content, _get_llm,
                graph_scope=graph_scope, client_api_key=client_api_key,
                provider=client_provider, model=client_model,
                base_url=client_base_url,
            )

    except WebSocketDisconnect:
        # Cancel any pending debounced save — we'll do a final save now
        old_task = _pending_saves.pop(session_id, None)
        if old_task and not old_task.done():
            old_task.cancel()

        session_service.save_session(session_id)
        try:
            await session_service.save_session_to_memory(session_id)
        except Exception:
            logger.exception("Failed to save session %s to memory", session_id)
        # Don't delete the session from memory — it may be resumed on reconnect.
        # Sessions are cleaned up when a new session is explicitly created or
        # the server restarts.
    finally:
        if _connection_llm is not None:
            try:
                await _connection_llm.close()
            except Exception:
                pass
