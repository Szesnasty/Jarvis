from fastapi import APIRouter

from services import graph_service

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
    return graph_service.get_neighbors(node_id, depth)


@router.post("/rebuild")
async def rebuild_graph():
    graph_service.invalidate_cache()
    graph = graph_service.rebuild_graph()
    return graph.stats()
