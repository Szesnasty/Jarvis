import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

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


def record_note_access(session_id: str, note_path: str) -> None:
    """Track which notes were read/written during this session."""
    session = _sessions.get(session_id)
    if not session:
        return
    session.setdefault("notes_accessed", set()).add(note_path)


def _get_workspace_path(workspace_path: Optional[Path]) -> Path:
    if workspace_path is not None:
        return workspace_path
    return get_settings().workspace_path


def save_session(session_id: str, workspace_path: Optional[Path] = None) -> None:
    session = _sessions.get(session_id)
    if not session:
        return

    messages = session["messages"]
    # Don't persist sessions with no messages
    if not messages:
        return

    ws = _get_workspace_path(workspace_path)
    sessions_dir = ws / "app" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

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
        "notes_accessed": sorted(session.get("notes_accessed", set())),
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
        "notes_accessed": set(data.get("notes_accessed", [])),
    }
    return session_id


def delete_session_file(session_id: str, workspace_path: Optional[Path] = None) -> None:
    d = _get_workspace_path(workspace_path) / "app" / "sessions"
    filepath = d / f"{session_id}.json"
    if filepath.exists():
        filepath.unlink()


# ---------------------------------------------------------------------------
# Conversation → Memory pipeline
# ---------------------------------------------------------------------------

# Tool name → semantic tag mapping
_TOOL_TAG_MAP = {
    "search_notes": "research",
    "read_note": "research",
    "write_note": "writing",
    "append_note": "writing",
    "create_plan": "planning",
    "update_plan": "planning",
    "summarize_context": "summary",
    "save_preference": "preferences",
    "query_graph": "knowledge-graph",
}


def _extract_topics(messages: List[dict]) -> List[str]:
    """Extract topic keywords from user messages using simple heuristics."""
    user_text = " ".join(
        m["content"] for m in messages if m["role"] == "user"
    ).lower()

    # Common stop words to skip
    stop = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very", "just", "about", "up", "it",
        "its", "i", "me", "my", "we", "our", "you", "your", "he", "she",
        "they", "them", "this", "that", "what", "which", "who", "or", "and",
        "but", "if", "because", "also", "like", "get", "got", "make", "don",
        "nie", "się", "jest", "to", "na", "co", "jak", "czy", "tak", "ten",
        "te", "tym", "ale", "też", "już", "mi", "mam", "być", "ma", "ze",
        "od", "po", "za", "do", "przy", "dla", "aby", "bo", "więc",
    }

    # Extract words 4+ chars, not stop words
    words = re.findall(r"\b[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{4,}\b", user_text)
    freq: Dict[str, int] = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1

    # Top 5 by frequency
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:5]]


def _extract_tags(session: dict) -> List[str]:
    """Extract tags from tools used + topics."""
    tags: Set[str] = {"conversation"}
    for tool in session.get("tools_used", set()):
        tag = _TOOL_TAG_MAP.get(tool)
        if tag:
            tags.add(tag)
    return sorted(tags)


def _generate_title(messages: List[dict]) -> str:
    """Generate a title from the first user message."""
    for msg in messages:
        if msg["role"] == "user":
            text = msg["content"].strip()
            # Take first sentence or first 80 chars
            first_line = text.split("\n")[0]
            if len(first_line) > 80:
                return first_line[:77] + "..."
            return first_line
    return "Untitled conversation"


def _format_conversation_body(
    messages: List[dict],
    notes_accessed: List[str],
    topics: List[str],
) -> str:
    """Format conversation messages as readable Markdown."""
    parts: List[str] = []

    # Conversation transcript
    parts.append("## Conversation\n")
    for msg in messages:
        role = "**User**" if msg["role"] == "user" else "**Jarvis**"
        content = msg["content"].strip()
        # Truncate very long messages
        if len(content) > 1000:
            content = content[:997] + "..."
        parts.append(f"{role}: {content}\n")

    # Related notes section with wiki links for graph connectivity
    if notes_accessed:
        parts.append("\n## Related Notes\n")
        for path in sorted(notes_accessed):
            # Use wiki-link syntax so graph picks up the connection
            label = Path(path).stem.replace("-", " ").replace("_", " ").title()
            parts.append(f"- [[{path}|{label}]]")

    # Topics for searchability
    if topics:
        parts.append(f"\n## Topics\n")
        parts.append(", ".join(topics))

    return "\n".join(parts)


async def save_session_to_memory(
    session_id: str,
    workspace_path: Optional[Path] = None,
) -> Optional[str]:
    """Convert a session into a Markdown note in memory/conversations/.

    Returns the note path, or None if session is too short to save.
    """
    session = _sessions.get(session_id)
    if not session:
        return None

    messages = session.get("messages", [])
    # Skip trivial sessions (fewer than 2 messages = no real conversation)
    if len(messages) < 2:
        return None

    from services import memory_service, graph_service

    ws = workspace_path
    now = datetime.now(timezone.utc)
    created = session.get("created_at", now.isoformat())

    title = _generate_title(messages)
    tags = _extract_tags(session)
    topics = _extract_topics(messages)
    notes_accessed = sorted(session.get("notes_accessed", set()))

    # Add topic words as extra tags (max 3)
    for topic in topics[:3]:
        if topic not in tags:
            tags.append(topic)

    # Build frontmatter
    date_slug = now.strftime("%Y-%m-%d")
    time_slug = now.strftime("%H%M")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40].strip("-")
    note_path = f"conversations/{date_slug}-{time_slug}-{slug}.md"

    fm = {
        "title": title,
        "type": "conversation",
        "session_id": session_id,
        "created_at": created,
        "updated_at": now.isoformat(),
        "tags": tags,
        "related": notes_accessed,
        "tools_used": sorted(session.get("tools_used", set())),
        "message_count": len(messages),
    }

    body = _format_conversation_body(messages, notes_accessed, topics)

    from utils.markdown import add_frontmatter

    content = add_frontmatter(body, fm)

    # Save to memory/conversations/
    mem = (ws or get_settings().workspace_path) / "memory"
    file_path = mem / note_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    # Index in SQLite
    try:
        await memory_service.index_note_file(note_path, workspace_path=ws)
    except Exception:
        pass  # Don't fail if indexing fails

    # Update knowledge graph to include the new conversation node
    try:
        graph_service.rebuild_graph(workspace_path=ws)
    except Exception:
        pass  # Don't fail if graph rebuild fails

    return note_path
