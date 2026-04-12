import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MAX_HISTORY_MESSAGES = 20

_sessions: dict[str, dict] = {}


def create_session() -> str:
    """Create a new session and return its ID."""
    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = {
        "id": session_id,
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    return _sessions.get(session_id)


def add_message(session_id: str, role: str, content: str) -> None:
    """Add a message to session history, trimming if needed."""
    session = _sessions.get(session_id)
    if not session:
        return

    session["messages"].append({"role": role, "content": content})

    if len(session["messages"]) > MAX_HISTORY_MESSAGES:
        session["messages"] = session["messages"][-MAX_HISTORY_MESSAGES:]


def get_messages(session_id: str) -> list[dict]:
    session = _sessions.get(session_id)
    if not session:
        return []
    return list(session["messages"])


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def save_session(session_id: str, workspace_path: Optional[Path] = None) -> None:
    """Save session to disk."""
    session = _sessions.get(session_id)
    if not session:
        return

    if workspace_path is None:
        from config import get_settings

        workspace_path = get_settings().workspace_path

    sessions_dir = workspace_path / "app" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    filepath = sessions_dir / f"{session_id}.json"
    filepath.write_text(json.dumps(session, indent=2), encoding="utf-8")
