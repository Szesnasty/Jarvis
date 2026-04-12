import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services import session_service
from services.claude import ClaudeService, StreamEvent, build_system_prompt
from services.tools import TOOLS, ToolNotFoundError, execute_tool
from services.workspace_service import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _send_event(ws: WebSocket, event_type: str, **fields) -> None:
    await ws.send_json({"type": event_type, **fields})


async def _run_tool(event: StreamEvent) -> str:
    try:
        return await execute_tool(event.name, event.tool_input or {})
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


async def _stream_follow_up(
    ws: WebSocket,
    claude: ClaudeService,
    tool_messages: list[dict],
    system_prompt: str,
) -> str:
    """Stream Claude's follow-up after tool execution. Returns accumulated text."""
    text = ""
    async for event in claude.stream_response(
        messages=tool_messages,
        system_prompt=system_prompt,
        tools=TOOLS,
    ):
        if event.type == "text_delta":
            text += event.content
            await _send_event(ws, "text_delta", content=event.content)
        elif event.type == "error":
            await _send_event(ws, "error", content=event.content)
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
    claude = ClaudeService(api_key=api_key)
    assistant_text = ""

    async for event in claude.stream_response(
        messages=messages,
        system_prompt=system_prompt,
        tools=TOOLS,
    ):
        if event.type == "text_delta":
            assistant_text += event.content
            await _send_event(ws, "text_delta", content=event.content)

        elif event.type == "tool_use":
            await _send_event(ws, "tool_use", name=event.name, input=event.tool_input)
            result = await _run_tool(event)
            await _send_event(ws, "tool_result", name=event.name, content=result)

            tool_messages = _build_tool_messages(messages, event, result)
            assistant_text += await _stream_follow_up(
                ws, claude, tool_messages, system_prompt,
            )

        elif event.type == "error":
            await _send_event(ws, "error", content=event.content)

    if assistant_text:
        session_service.add_message(session_id, "assistant", assistant_text)

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
        session_service.delete_session(session_id)
