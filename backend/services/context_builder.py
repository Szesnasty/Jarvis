from typing import Optional

from services import memory_service, preference_service, retrieval


async def build_context(
    user_message: str,
    workspace_path=None,
) -> Optional[str]:
    """Build a small context string from relevant notes and preferences."""
    parts = []

    prefs_text = preference_service.format_for_prompt(workspace_path)
    if prefs_text:
        parts.append(prefs_text)

    results = await retrieval.retrieve(
        user_message,
        limit=5,
        workspace_path=workspace_path,
    )

    if results:
        note_parts = []
        for result in results[:3]:
            path = result.get("path", "")
            if not path:
                continue
            try:
                note = await memory_service.get_note(path, workspace_path=workspace_path)
                truncated = note["content"][:500]
                note_parts.append(f"[{path}]\n{truncated}")
            except Exception:
                continue
        if note_parts:
            parts.append("\n---\n".join(note_parts))

    return "\n\n".join(parts) if parts else None
