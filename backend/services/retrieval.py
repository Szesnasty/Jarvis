from typing import Dict, List, Optional

from services import graph_service, memory_service


async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> List[Dict]:
    """Hybrid retrieval: FTS search + graph expansion + ranking."""
    if not query or not query.strip():
        return []

    # 1. Structural search (SQLite FTS)
    search_results = await memory_service.list_notes(
        search=query,
        limit=limit * 2,
        workspace_path=workspace_path,
    )

    # 2. Graph expansion
    expanded: Dict[str, Dict] = {}
    for result in search_results[:3]:
        note_id = f"note:{result['path']}"
        neighbors = graph_service.get_neighbors(note_id, depth=1, workspace_path=workspace_path)
        for neighbor in neighbors:
            if neighbor["type"] == "note" and neighbor["id"].startswith("note:"):
                path = neighbor["id"][5:]  # strip "note:"
                if path not in expanded:
                    expanded[path] = {"path": path, "label": neighbor["label"], "source": "graph"}

    # 3. Merge + deduplicate
    seen_paths = {r["path"] for r in search_results}
    merged = list(search_results)
    for path, info in expanded.items():
        if path not in seen_paths:
            merged.append(info)
            seen_paths.add(path)

    # 4. Rank: direct FTS matches first, then graph expansions
    def _rank(item: Dict) -> int:
        if item.get("source") == "graph":
            return 1
        return 0

    merged.sort(key=_rank)
    return merged[:limit]
