from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import graph_service, memory_service
from utils.markdown import parse_frontmatter, add_frontmatter

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
async def get_graph():
    graph = graph_service.load_graph()
    if graph is None:
        return {"nodes": [], "edges": []}
    return graph.to_dict()


@router.get("/stats")
async def get_stats():
    graph = graph_service.load_graph()
    if graph is None:
        return {"node_count": 0, "edge_count": 0, "top_connected": []}
    return graph.stats()


@router.get("/neighbors")
async def get_neighbors(node_id: str, depth: int = 1):
    depth = max(1, min(depth, 5))  # cap depth to prevent DoS
    return graph_service.get_neighbors(node_id, depth)


@router.get("/nodes/{node_id:path}/detail")
async def get_node_detail(node_id: str):
    detail = graph_service.get_node_detail(node_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return detail


@router.get("/orphans")
async def get_orphans():
    return graph_service.find_orphans()


class EdgeCreate(BaseModel):
    source: str
    target: str
    type: str = "related"


@router.post("/edges")
async def create_edge(body: EdgeCreate):
    """Create a manual edge by updating the source note's frontmatter."""
    if body.type not in ("related", "linked"):
        raise HTTPException(status_code=400, detail="Edge type must be 'related' or 'linked'")
    if not body.source.startswith("note:") or not body.target.startswith("note:"):
        raise HTTPException(status_code=400, detail="Both source and target must be note: IDs")

    source_path = body.source[5:]  # strip "note:"
    target_path = body.target[5:]

    try:
        note = await memory_service.get_note(source_path)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Source note not found: {source_path}")

    # Update frontmatter related list
    fm, note_body = parse_frontmatter(note["content"])
    related = fm.get("related", [])
    if target_path not in related:
        related.append(target_path)
        fm["related"] = related
        new_content = add_frontmatter(note_body, fm)
        await memory_service.update_note(source_path, new_content)

    # Rebuild graph to pick up the new edge
    import asyncio
    graph_service.invalidate_cache()
    await asyncio.to_thread(graph_service.rebuild_graph)

    return {"status": "ok", "edge": {"source": body.source, "target": body.target, "type": body.type}}


@router.post("/rebuild")
async def rebuild_graph():
    import asyncio
    graph_service.invalidate_cache()
    graph = await asyncio.to_thread(graph_service.rebuild_graph)
    return graph.stats()
