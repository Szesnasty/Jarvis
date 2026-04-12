import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from config import get_settings


MAX_HISTORY_MESSAGES = 20

_sessions: dict[str, dict] = {}


class SessionNotFoundError(Exception):
    pass


def create_session() -> str:
    """Create a new session and return its ID."""
    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = {
        "id": session_id,
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tools_used": set(),
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


def record_tool_use(session_id: str, tool_name: str) -> None:
    session = _sessions.get(session_id)
    if not session:
        return
    session.setdefault("tools_used", set()).add(tool_name)


def _get_workspace_path(workspace_path: Optional[Path]) -> Path:
    if workspace_path is not None:
        return workspace_path
    return get_settings().workspace_path


def save_session(session_id: str, workspace_path: Optional[Path] = None) -> None:
    session = _sessions.get(session_id)
    if not session:
        return

    ws = _get_workspace_path(workspace_path)
    sessions_dir = ws / "app" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    messages = session["messages"]
    title = ""
    for msg in messages:
        if msg["role"] == "user":
            title = msg["content"][:100]
            break

    data = {
        "session_id": session_id,
        "title": title,
        "created_at": session["created_at"],
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(messages),
        "messages": messages,
        "tools_used": sorted(session.get("tools_used", set())),
    }

    filepath = sessions_dir / f"{session_id}.json"
    filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_sessions(workspace_path: Optional[Path] = None) -> List[dict]:
    d = _get_workspace_path(workspace_path) / "app" / "sessions"
    if not d.exists():
        return []

    sessions = []
    for f in d.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        sessions.append({
            "session_id": data.get("session_id", f.stem),
            "title": data.get("title", ""),
            "created_at": data.get("created_at", ""),
            "message_count": data.get("message_count", 0),
        })

    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return sessions


def load_session(session_id: str, workspace_path: Optional[Path] = None) -> dict:
    d = _get_workspace_path(workspace_path) / "app" / "sessions"
    filepath = d / f"{session_id}.json"

    if not filepath.exists():
        raise SessionNotFoundError(f"Session not found: {session_id}")

    return json.loads(filepath.read_text(encoding="utf-8"))


def resume_session(session_id: str, workspace_path: Optional[Path] = None) -> str:
    data = load_session(session_id, workspace_path)
    _sessions[session_id] = {
        "id": session_id,
        "messages": data.get("messages", []),
        "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
        "tools_used": set(data.get("tools_used", [])),
    }
    return session_id


def delete_session_file(session_id: str, workspace_path: Optional[Path] = None) -> None:
    d = _get_workspace_path(workspace_path) / "app" / "sessions"
    filepath = d / f"{session_id}.json"
    if filepath.exists():
        filepath.unlink()
