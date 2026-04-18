"""MCP lifecycle API — start/stop SSE transport, status, token management."""

from __future__ import annotations

import logging
import socket
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import get_settings
from services.mcp.auth import ensure_token, regenerate_token
from services.mcp import mcp_logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# ---------------------------------------------------------------------------
# Module-level state for the SSE transport
# ---------------------------------------------------------------------------

_sse_transport: Any | None = None  # SSETransport instance
_mcp_server: Any | None = None


def _get_workspace() -> Path:
    return get_settings().workspace_path


def _get_mcp_config() -> dict[str, Any]:
    """Load MCP config from workspace config.json (if present)."""
    import json

    ws = _get_workspace()
    config_file = ws / "app" / "config.json"
    if not config_file.exists():
        return {}
    try:
        with config_file.open(encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mcp", {})
    except Exception:
        return {}


def _build_server():
    """Lazily build the MCP server singleton."""
    global _mcp_server
    if _mcp_server is not None:
        return _mcp_server

    from services.mcp.server import JarvisMCPServer, MCPConfig
    from services.mcp.tools import build_tools, set_workspace_path

    ws = _get_workspace()
    set_workspace_path(ws)

    mcp_cfg = _get_mcp_config()
    config = MCPConfig(
        workspace_path=ws,
        allow_writes=mcp_cfg.get("allow_writes", False),
        tool_budgets=mcp_cfg.get("tool_budgets", {}),
    )

    _mcp_server = JarvisMCPServer(build_tools(), config)
    return _mcp_server


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    transport: str = "sse"
    port: int = 8765


class StartResponse(BaseModel):
    ok: bool
    port: int
    tool_count: int


class StatusResponse(BaseModel):
    running: bool
    transport: str | None = None
    port: int | None = None
    token_set: bool = False
    tool_count: int = 0
    calls_today: int = 0
    last_call: str | None = None
    top_tool: str | None = None
    python_path: str = ""
    backend_dir: str = ""
    workspace_path: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=StatusResponse)
async def mcp_status() -> StatusResponse:
    ws = _get_workspace()
    token_file = ws / "app" / "mcp_token"
    stats = mcp_logging.get_stats(ws)

    server = _build_server()
    tool_count = len(server.list_tools())

    running = _sse_transport is not None and _sse_transport.running

    backend_dir = Path(__file__).parent.parent

    return StatusResponse(
        running=running,
        transport="sse" if running else None,
        port=_sse_transport._port if running else None,
        token_set=token_file.exists(),
        tool_count=tool_count,
        calls_today=stats.get("calls_today", 0),
        last_call=stats.get("last_call"),
        top_tool=stats.get("top_tool"),
        python_path=sys.executable,
        backend_dir=str(backend_dir),
        workspace_path=str(ws),
    )


@router.post("/start", response_model=StartResponse)
async def mcp_start(body: StartRequest) -> StartResponse:
    global _sse_transport

    if body.transport != "sse":
        raise HTTPException(400, "Only 'sse' transport can be started via API. Use 'python -m services.mcp --transport stdio' for stdio.")

    if _sse_transport is not None and _sse_transport.running:
        raise HTTPException(409, "MCP server already running")

    # Check port availability
    if not _port_available(body.port):
        raise HTTPException(409, f"Port {body.port} is already in use")

    ws = _get_workspace()
    token = ensure_token(ws)
    server = _build_server()

    from services.mcp.transports.sse import SSETransport

    _sse_transport = SSETransport(server, token=token, port=body.port)
    await _sse_transport.start()

    return StartResponse(
        ok=True,
        port=body.port,
        tool_count=len(server.list_tools()),
    )


@router.post("/stop")
async def mcp_stop() -> dict[str, bool]:
    global _sse_transport
    if _sse_transport is None or not _sse_transport.running:
        return {"ok": True}  # idempotent
    await _sse_transport.stop()
    _sse_transport = None
    return {"ok": True}


@router.post("/regenerate-token")
async def mcp_regenerate_token() -> dict[str, bool]:
    ws = _get_workspace()
    regenerate_token(ws)
    return {"ok": True}


@router.get("/token")
async def mcp_get_token() -> dict[str, str]:
    ws = _get_workspace()
    token = ensure_token(ws)
    return {"token": token}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False
