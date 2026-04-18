"""MCP auth — per-workspace bearer token generation and verification."""

from __future__ import annotations

import secrets
from pathlib import Path

TOKEN_FILE = "app/mcp_token"
TOKEN_BYTES = 32  # 256 bits → 43-char urlsafe string


def ensure_token(workspace_path: Path) -> str:
    """Return existing token or generate a new one (file mode 0o600)."""
    p = workspace_path / TOKEN_FILE
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(TOKEN_BYTES)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token, encoding="utf-8")
    p.chmod(0o600)
    return token


def regenerate_token(workspace_path: Path) -> str:
    """Rotate the token — old one becomes invalid immediately."""
    p = workspace_path / TOKEN_FILE
    if p.exists():
        p.unlink()
    return ensure_token(workspace_path)


def verify_bearer(header: str | None, expected: str) -> bool:
    """Constant-time comparison of an Authorization header against the expected token."""
    if not header or not header.startswith("Bearer "):
        return False
    return secrets.compare_digest(header[7:], expected)
