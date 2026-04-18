"""Workspace path discovery for the MCP server.

Resolution order:
1. Explicit `--workspace` CLI flag
2. `JARVIS_WORKSPACE` environment variable
3. `~/.jarvis/config.toml` → `workspace = "/path/to/jarvis"`
4. Default `~/Jarvis`
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path


CONFIG_FILE = Path.home() / ".jarvis" / "config.toml"
DEFAULT_WORKSPACE = Path.home() / "Jarvis"


def resolve_workspace(cli_arg: Path | None = None) -> Path:
    if cli_arg is not None:
        return cli_arg.expanduser().resolve()

    env = os.environ.get("JARVIS_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()

    if CONFIG_FILE.is_file():
        try:
            with CONFIG_FILE.open("rb") as fh:
                data = tomllib.load(fh)
            ws = data.get("workspace")
            if isinstance(ws, str) and ws:
                return Path(ws).expanduser().resolve()
        except (OSError, tomllib.TOMLDecodeError):
            pass

    return DEFAULT_WORKSPACE.resolve()


def write_config(workspace: Path) -> Path:
    """Persist the workspace path to ~/.jarvis/config.toml. Used by bootstrap."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(f'workspace = "{workspace.expanduser().resolve()}"\n', encoding="utf-8")
    return CONFIG_FILE
