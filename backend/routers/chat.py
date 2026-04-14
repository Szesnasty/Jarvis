import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import session_service
from services import specialist_service
from services.claude import ClaudeService, StreamEvent, build_system_prompt
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
    claude: ClaudeService,
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
            next_messages = _build_tool_messages(next_messages, tool_event, result)

        text += await _stream_follow_up(
            ws, claude, next_messages, system_prompt, tools,
            session_id, api_key, usage_acc, depth + 1,
        )

    return text


async def _handle_message(
    ws: WebSocket,
    session_id: str,
    content: str,
    get_claude: callable = None,
    graph_scope: Optional[str] = None,
) -> None:
    api_key = get_api_key()
    if not api_key:
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

    claude = get_claude(api_key) if get_claude else ClaudeService(api_key=api_key)
    assistant_text = ""
    # [input_tokens, output_tokens] accumulated across all rounds
    usage_acc = [0, 0]
    pending_tools: list[StreamEvent] = []

    async for event in claude.stream_response(
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
    ):
        if event.type == "text_delta":
            assistant_text += event.content
            await _send_event(ws, "text_delta", content=event.content)

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
            tool_messages = _build_tool_messages(tool_messages, tool_event, result)

        assistant_text += await _stream_follow_up(
            ws, claude, tool_messages, system_prompt, tools,
            session_id, api_key, usage_acc,
        )

    if assistant_text:
        session_service.add_message(session_id, "assistant", assistant_text)
    else:
        # No text response (e.g. pure tool-use) — still persist so session
        # state stays consistent, but add_message already auto-saves on the
        # user message so an extra save here is only needed when we have text.
        pass

    # Log token usage if we got any
    if usage_acc[0] > 0 or usage_acc[1] > 0:
        try:
            log_usage(usage_acc[0], usage_acc[1])
        except Exception:
            logger.warning("Failed to log token usage")

    await _send_event(ws, "done", session_id=session_id)


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

    content = data.get("content", "").strip()
    if not content:
        return None, "Message content is required"

    return data, None


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
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

    # Reuse a single ClaudeService per connection to avoid per-message HTTP pool churn
    _connection_claude: ClaudeService | None = None

    def _get_claude(api_key: str) -> ClaudeService:
        nonlocal _connection_claude
        if _connection_claude is None:
            _connection_claude = ClaudeService(api_key=api_key)
        return _connection_claude

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

            content = data.get("content", "").strip()

            requested_sid = data.get("session_id")
            if requested_sid and requested_sid != session_id:
                if session_service.get_session(requested_sid):
                    session_id = requested_sid

            graph_scope = data.get("graph_scope") or None
            await _handle_message(websocket, session_id, content, _get_claude, graph_scope=graph_scope)

    except WebSocketDisconnect:
        session_service.save_session(session_id)
        try:
            await session_service.save_session_to_memory(session_id)
        except Exception:
            logger.exception("Failed to save session %s to memory", session_id)
        # Don't delete the session from memory — it may be resumed on reconnect.
        # Sessions are cleaned up when a new session is explicitly created or
        # the server restarts.
    finally:
        if _connection_claude is not None:
            try:
                await _connection_claude.close()
            except Exception:
                pass
