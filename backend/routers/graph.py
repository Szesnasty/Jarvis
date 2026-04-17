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


class MergeRequest(BaseModel):
    source_id: str
    target_id: str
    entity_type: str = "person"


@router.post("/merge-entities")
async def merge_entities_endpoint(body: MergeRequest):
    """Manually merge two entity nodes."""
    import asyncio
    from services.entity_canonicalization import merge_entities

    db_path = memory_service._db_path()
    await merge_entities(body.source_id, body.target_id, body.entity_type, db_path)
    # Rebuild graph to reflect merge
    graph_service.invalidate_cache()
    await asyncio.to_thread(graph_service.rebuild_graph)
    return {"status": "ok", "merged": body.source_id, "into": body.target_id}


@router.get("/merge-candidates")
async def get_merge_candidates(entity_type: str = "person"):
    """Find pairs of entities that might be duplicates."""
    from services.entity_canonicalization import find_merge_candidates

    db_path = memory_service._db_path()
    return await find_merge_candidates(entity_type, db_path)


@router.post("/rebuild-soft")
async def rebuild_soft_edges_endpoint():
    """Rebuild all derived (soft) edges. Returns stats."""
    import asyncio
    from services.graph_service.soft_edges import rebuild_soft_edges
    from config import get_settings

    graph = graph_service.load_graph()
    if graph is None:
        graph_service.invalidate_cache()
        graph = await asyncio.to_thread(graph_service.rebuild_graph)

    ws = get_settings().workspace_path
    count = await asyncio.to_thread(rebuild_soft_edges, ws, graph)

    # Save the updated graph
    from services.graph_service.builder import _save_and_cache
    _save_and_cache(graph)

    return {"status": "ok", "edges_added": count}


@router.get("/edges")
async def get_edges(origin: str = None, type: str = None):
    """List edges with optional origin/type filters."""
    graph = graph_service.load_graph()
    if graph is None:
        return []

    edges = graph.edges
    if origin:
        edges = [e for e in edges if e.origin == origin]
    if type:
        edges = [e for e in edges if e.type == type]

    result = []
    for e in edges:
        d = {"source": e.source, "target": e.target, "type": e.type, "weight": e.weight}
        if e.origin != "generic":
            d["origin"] = e.origin
        if e.evidence:
            d["evidence"] = [
                {"source_chunk": sc, "target_chunk": tc, "similarity": round(sim, 3)}
                for sc, tc, sim in e.evidence
            ]
        result.append(d)
    return result
