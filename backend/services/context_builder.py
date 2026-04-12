from typing import List, Optional

from services import memory_service, preference_service, retrieval


def _scope_results(results: List[dict], sources: List[str]) -> List[dict]:
    """Filter results to only those within specialist source folders."""
    if not sources:
        return results
    scoped = []
    for r in results:
        path = r.get("path", "")
        for source in sources:
            prefix = source.replace("memory/", "")
            if path.startswith(prefix):
                scoped.append(r)
                break
    return scoped


async def build_context(
    user_message: str,
    workspace_path=None,
) -> Optional[str]:
    """Build a small context string from relevant notes and preferences."""
    from services import specialist_service

    parts = []

    prefs_text = preference_service.format_for_prompt(workspace_path)
    if prefs_text:
        parts.append(prefs_text)

    results = await retrieval.retrieve(
        user_message,
        limit=5,
        workspace_path=workspace_path,
    )

    active = specialist_service.get_active_specialist()
    if active and active.get("sources"):
        results = _scope_results(results, active["sources"])

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
