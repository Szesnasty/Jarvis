from typing import Optional

from services import memory_service


async def build_context(
    user_message: str,
    workspace_path=None,
) -> Optional[str]:
    """Build a small context string from relevant notes."""
    results = await memory_service.list_notes(
        search=user_message,
        limit=5,
        workspace_path=workspace_path,
    )

    if not results:
        return None

    context_parts = []
    for result in results[:3]:
        note = await memory_service.get_note(
            result["path"],
            workspace_path=workspace_path,
        )
        truncated = note["content"][:500]
        context_parts.append(f"[{result['path']}]\n{truncated}")

    return "\n---\n".join(context_parts)
