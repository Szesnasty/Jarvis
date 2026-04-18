"""MCP SSE transport — HTTP server with Server-Sent Events for MCP messages."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from services.mcp.auth import verify_bearer
from services.mcp.server import (
    JarvisMCPServer,
    MCPError,
    UnknownToolError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class SSETransport:
    """Starlette-based SSE transport for MCP.

    Endpoints:
    - GET  /sse          → SSE stream (sends endpoint URL, then tool results)
    - POST /messages     → receives JSON-RPC requests
    """

    def __init__(self, server: JarvisMCPServer, *, token: str, host: str = "127.0.0.1", port: int = 8765) -> None:
        self._server = server
        self._token = token
        self._host = host
        self._port = port
        self._sessions: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._app: Starlette | None = None
        self._server_task: asyncio.Task[None] | None = None

    def _check_auth(self, request: Request) -> bool:
        header = request.headers.get("authorization")
        return verify_bearer(header, self._token)

    async def _sse_endpoint(self, request: Request) -> Response:
        if not self._check_auth(request):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        session_id = uuid.uuid4().hex[:12]
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._sessions[session_id] = queue

        async def event_generator():
            # Send the endpoint URL as the first event
            endpoint_url = f"http://{self._host}:{self._port}/messages?session_id={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"

            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"event: message\ndata: {json.dumps(msg, default=str)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                self._sessions.pop(session_id, None)

        from starlette.responses import StreamingResponse

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def _messages_endpoint(self, request: Request) -> Response:
        if not self._check_auth(request):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        session_id = request.query_params.get("session_id", "")
        queue = self._sessions.get(session_id)
        if queue is None:
            return JSONResponse({"error": "Invalid session"}, status_code=404)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        msg_id = body.get("id")
        method = body.get("method", "")
        params = body.get("params", {})

        try:
            if method == "initialize":
                result = self._server.initialize()
                response = {"jsonrpc": "2.0", "id": msg_id, "result": result}

            elif method == "tools/list":
                tools = self._server.list_tools()
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = await self._server.call_tool(
                    name, arguments, client_id=f"sse:{session_id}"
                )
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                        "isError": False,
                    },
                }

            elif method == "ping":
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            elif method == "notifications/initialized":
                return JSONResponse({"ok": True}, status_code=200)

            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

        except (UnknownToolError, ValidationError, MCPError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }
        except Exception as exc:
            logger.exception("SSE transport error")
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Internal error: {type(exc).__name__}"},
            }

        await queue.put(response)
        return JSONResponse({"ok": True}, status_code=202)

    def build_app(self) -> Starlette:
        self._app = Starlette(
            routes=[
                Route("/sse", self._sse_endpoint),
                Route("/messages", self._messages_endpoint, methods=["POST"]),
            ],
        )
        return self._app

    async def start(self) -> None:
        """Start the SSE server as a background task."""
        import uvicorn

        app = self.build_app()
        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(server.serve())
        logger.info("MCP SSE server started on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the SSE server."""
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
            self._server_task = None
            logger.info("MCP SSE server stopped")

    @property
    def running(self) -> bool:
        return self._server_task is not None and not self._server_task.done()
