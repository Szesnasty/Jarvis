from typing import Optional

from services import memory_service, preference_service


async def build_context(
    user_message: str,
    workspace_path=None,
) -> Optional[str]:
    """Build a small context string from relevant notes and preferences."""
    parts = []

    prefs_text = preference_service.format_for_prompt(workspace_path)
    if prefs_text:
        parts.append(prefs_text)

    results = await memory_service.list_notes(
        search=user_message,
        limit=5,
        workspace_path=workspace_path,
    )

    if results:
        note_parts = []
        for result in results[:3]:
            note = await memory_service.get_note(
                result["path"],
                workspace_path=workspace_path,
            )
            truncated = note["content"][:500]
            note_parts.append(f"[{result['path']}]\n{truncated}")
        parts.append("\n---\n".join(note_parts))

    return "\n\n".join(parts) if parts else None
