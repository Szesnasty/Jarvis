"""MCP runner — CLI entrypoint for standalone MCP transports.

Usage:
    python -m services.mcp --transport stdio
    python -m services.mcp --transport sse --port 8765
    python -m services.mcp --help
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="jarvis-mcp",
        description="Jarvis MCP Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE transport")
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE transport")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace path (default: from JARVIS_WORKSPACE_PATH or ~/Jarvis)",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        default=False,
        help="Enable write tools (save_preference, append_note, summarize_and_save)",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=None,
        help="Path to MCP token file (SSE only, default: workspace/app/mcp_token)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,  # keep stdout clean for stdio transport
    )

    # Resolve workspace path
    if args.workspace:
        workspace_path = args.workspace.resolve()
    else:
        from config import get_settings
        workspace_path = get_settings().workspace_path

    # Build server
    from services.mcp.server import JarvisMCPServer, MCPConfig
    from services.mcp.tools import build_tools, set_workspace_path

    set_workspace_path(workspace_path)

    config = MCPConfig(
        workspace_path=workspace_path,
        allow_writes=args.allow_writes,
    )
    server = JarvisMCPServer(build_tools(), config)

    if args.transport == "stdio":
        from services.mcp.transports.stdio import StdioTransport

        transport = StdioTransport(server)
        asyncio.run(transport.run())

    elif args.transport == "sse":
        from services.mcp.auth import ensure_token
        from services.mcp.transports.sse import SSETransport

        if args.token_file and args.token_file.exists():
            token = args.token_file.read_text(encoding="utf-8").strip()
        else:
            token = ensure_token(workspace_path)

        transport = SSETransport(  # type: ignore[assignment]
            server, token=token, host=args.host, port=args.port
        )

        async def _run_sse():
            await transport.start()
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(3600)
            except asyncio.CancelledError:
                await transport.stop()

        try:
            asyncio.run(_run_sse())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
