import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import session_service
from services import specialist_service
from services.claude import ClaudeService, StreamEvent, build_system_prompt
from services.tools import TOOLS, ToolNotFoundError, execute_tool
from services.token_tracking import log_usage
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
    pending_tool: StreamEvent | None = None

    async for event in claude.stream_response(
        messages=tool_messages,
        system_prompt=system_prompt,
        tools=tools,
    ):
        if event.type == "text_delta":
            text += event.content
            await _send_event(ws, "text_delta", content=event.content)
        elif event.type == "tool_use":
            pending_tool = event
        elif event.type == "usage":
            usage_acc[0] += event.input_tokens
            usage_acc[1] += event.output_tokens
        elif event.type == "error":
            await _send_event(ws, "error", content=event.content)

    # If Claude wants another tool call, execute it and recurse
    if pending_tool is not None and depth < MAX_TOOL_ROUNDS:
        await _send_event(ws, "tool_use", name=pending_tool.name, input=pending_tool.tool_input)
        session_service.record_tool_use(session_id, pending_tool.name)
        result = await _run_tool(pending_tool, session_id=session_id, api_key=api_key)
        await _send_event(ws, "tool_result", name=pending_tool.name, content=result)

        next_messages = _build_tool_messages(tool_messages, pending_tool, result)
        text += await _stream_follow_up(
            ws, claude, next_messages, system_prompt, tools,
            session_id, api_key, usage_acc, depth + 1,
        )

    return text


async def _handle_message(
    ws: WebSocket,
    session_id: str,
    content: str,
) -> None:
    api_key = get_api_key()
    if not api_key:
        await _send_event(ws, "error", content="API key not configured")
        return

    session_service.add_message(session_id, "user", content)
    messages = session_service.get_messages(session_id)
    system_prompt = await build_system_prompt(content)
    active_spec = specialist_service.get_active_specialist()
    tools = specialist_service.filter_tools(TOOLS, active_spec)
    claude = ClaudeService(api_key=api_key)
    assistant_text = ""
    # [input_tokens, output_tokens] accumulated across all rounds
    usage_acc = [0, 0]
    pending_tool: StreamEvent | None = None

    async for event in claude.stream_response(
        messages=messages,
        system_prompt=system_prompt,
        tools=tools,
    ):
        if event.type == "text_delta":
            assistant_text += event.content
            await _send_event(ws, "text_delta", content=event.content)

        elif event.type == "tool_use":
            pending_tool = event

        elif event.type == "usage":
            usage_acc[0] += event.input_tokens
            usage_acc[1] += event.output_tokens

        elif event.type == "error":
            await _send_event(ws, "error", content=event.content)

    # Handle tool call chain (up to MAX_TOOL_ROUNDS)
    if pending_tool is not None:
        await _send_event(ws, "tool_use", name=pending_tool.name, input=pending_tool.tool_input)
        session_service.record_tool_use(session_id, pending_tool.name)
        result = await _run_tool(pending_tool, session_id=session_id, api_key=api_key)
        await _send_event(ws, "tool_result", name=pending_tool.name, content=result)

        tool_messages = _build_tool_messages(messages, pending_tool, result)
        assistant_text += await _stream_follow_up(
            ws, claude, tool_messages, system_prompt, tools,
            session_id, api_key, usage_acc,
        )

    if assistant_text:
        session_service.add_message(session_id, "assistant", assistant_text)

    # Log token usage if we got any
    if usage_acc[0] > 0 or usage_acc[1] > 0:
        try:
            log_usage(usage_acc[0], usage_acc[1])
        except Exception:
            logger.warning("Failed to log token usage")

    # Auto-save session after each exchange for crash protection
    try:
        session_service.save_session(session_id)
    except Exception:
        pass

    await _send_event(ws, "done", session_id=session_id)


def _parse_message(raw: str) -> tuple:
    """Parse raw WS text. Returns (data, error_message)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "Invalid JSON"

    content = data.get("content", "").strip()
    if not content:
        return None, "Message content is required"

    return data, None


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    session_id = session_service.create_session()
    await _send_event(websocket, "session_start", session_id=session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            data, error = _parse_message(raw)

            if error:
                await _send_event(websocket, "error", content=error)
                continue

            content = data.get("content", "").strip()

            requested_sid = data.get("session_id")
            if requested_sid and requested_sid != session_id:
                if session_service.get_session(requested_sid):
                    session_id = requested_sid

            await _handle_message(websocket, session_id, content)

    except WebSocketDisconnect:
        session_service.save_session(session_id)
        try:
            await session_service.save_session_to_memory(session_id)
        except Exception:
            logger.exception("Failed to save session %s to memory", session_id)
        session_service.delete_session(session_id)
