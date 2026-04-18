"""CLI entry point: `jarvis-mcp`.

Standalone stdio MCP server. Self-contained — works from any directory.

Usage:
    jarvis-mcp                                 # stdio, default workspace
    jarvis-mcp --workspace ~/somewhere/else
    jarvis-mcp --allow-writes
    jarvis-mcp --verbose
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make sibling packages (services, config, etc.) importable when running as a
# console script. The Path.parent.parent climb resolves to the backend root.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from mcp_server.app import build_app  # noqa: E402
from mcp_server.config import resolve_workspace  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(prog="jarvis-mcp", description="Jarvis MCP Server (stdio)")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace path. Default: $JARVIS_WORKSPACE / ~/.jarvis/config.toml / ~/Jarvis",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        help="Enable write tools (save_preference, append_note, summarize_and_save)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Transport (only stdio supported)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging to stderr")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    workspace = resolve_workspace(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    logging.getLogger(__name__).info("jarvis-mcp starting (workspace=%s, writes=%s)", workspace, args.allow_writes)

    app = build_app(workspace, allow_writes=args.allow_writes)
    app.run()  # FastMCP defaults to stdio


if __name__ == "__main__":
    main()
