"""MCP call logger — append-only JSONL at app/logs/mcp.jsonl."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOG_DIR_NAME = "app/logs"
_LOG_FILE_NAME = "mcp.jsonl"

_current_day: str | None = None
_log_path: Path | None = None


def _resolve_log_path(workspace_path: Path) -> Path:
    """Ensure the log dir exists and rotate if the day has changed."""
    global _current_day, _log_path

    log_dir = workspace_path / _LOG_DIR_NAME
    log_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    current_file = log_dir / _LOG_FILE_NAME

    if _current_day is not None and _current_day != today and current_file.exists():
        rotated = log_dir / f"mcp-{_current_day}.jsonl"
        try:
            current_file.rename(rotated)
        except OSError:
            pass  # already rotated or concurrent access

    _current_day = today
    _log_path = current_file
    return _log_path


def hash_args(args: dict[str, Any]) -> str:
    """Deterministic hash of tool arguments (for privacy — don't log raw args)."""
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _write_entry(workspace_path: Path, entry: dict[str, Any]) -> None:
    path = _resolve_log_path(workspace_path)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError as exc:
        logger.warning("Failed to write MCP log: %s", exc)


@asynccontextmanager
async def log_call(
    workspace_path: Path,
    *,
    tool: str,
    args: dict[str, Any],
    client_id: str = "unknown",
):
    """Context manager that logs the tool call start/end with timing."""
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "args_hash": hash_args(args),
        "client": client_id,
    }
    t0 = time.monotonic()
    error: str | None = None
    try:
        yield entry
    except Exception as exc:
        error = type(exc).__name__
        raise
    finally:
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        entry["elapsed_ms"] = elapsed_ms
        entry["output_tokens"] = entry.get("output_tokens", 0)
        if error:
            entry["error"] = error
        _write_entry(workspace_path, entry)


def get_stats(workspace_path: Path) -> dict[str, Any]:
    """Aggregate stats from today's log file for the status endpoint."""
    log_file = _resolve_log_path(workspace_path)
    stats: dict[str, Any] = {"calls_today": 0, "last_call": None, "top_tool": None}
    if not log_file.exists():
        return stats

    tool_counts: dict[str, int] = {}
    last_ts: str | None = None
    count = 0
    try:
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            t = rec.get("tool", "?")
            tool_counts[t] = tool_counts.get(t, 0) + 1
            last_ts = rec.get("ts", last_ts)
    except OSError:
        return stats

    stats["calls_today"] = count
    stats["last_call"] = last_ts
    if tool_counts:
        stats["top_tool"] = max(tool_counts, key=tool_counts.get)  # type: ignore[arg-type]
    return stats
