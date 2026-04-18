"""Knowledge graph tools — query entities, neighbors, paths."""

from __future__ import annotations

import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server.middleware.audit import audit
from mcp_server.middleware.budget import enforce_budget


def register(mcp: FastMCP, *, workspace: Path) -> None:
    ws = lambda: workspace  # noqa: E731

    @mcp.tool(
        name="jarvis_graph_query",
        description="Query the knowledge graph around a free-text entity. Returns neighbors with edge types.",
    )
    @audit("jarvis_graph_query", ws)
    @enforce_budget(max_tokens=2000)
    async def jarvis_graph_query(
        entity: str,
        relation_type: str | None = None,
        depth: int = 1,
    ) -> dict:
        from services.graph_service.queries import query_entity

        neighbors = await asyncio.to_thread(
            query_entity, entity, relation_type=relation_type, depth=depth, workspace_path=workspace
        )
        return {"entity": entity, "results": neighbors}

    @mcp.tool(
        name="jarvis_graph_neighbors",
        description="Get neighbors of a canonical graph node ID (e.g. 'person:adam-nowak').",
    )
    @audit("jarvis_graph_neighbors", ws)
    @enforce_budget(max_tokens=2000)
    async def jarvis_graph_neighbors(node_id: str, depth: int = 1) -> dict:
        from services.graph_service.queries import get_neighbors

        neighbors = await asyncio.to_thread(
            get_neighbors, node_id, depth=depth, workspace_path=workspace
        )
        return {"node_id": node_id, "results": neighbors}

    @mcp.tool(
        name="jarvis_graph_entity_detail",
        description="Full details about a graph node: aliases, mentions, top related notes/issues.",
    )
    @audit("jarvis_graph_entity_detail", ws)
    @enforce_budget(max_tokens=1500)
    async def jarvis_graph_entity_detail(node_id: str) -> dict:
        from services.graph_service.queries import get_node_detail

        detail = await asyncio.to_thread(get_node_detail, node_id, workspace_path=workspace)
        if detail is None:
            return {"error": f"Node '{node_id}' not found"}
        return detail

    @mcp.tool(
        name="jarvis_graph_path_between",
        description="Find shortest path between two entities in the knowledge graph.",
    )
    @audit("jarvis_graph_path_between", ws)
    @enforce_budget(max_tokens=1500)
    async def jarvis_graph_path_between(
        source: str,
        target: str,
        max_depth: int = 4,
    ) -> dict:
        from services.graph_service.queries import get_neighbors

        visited: set[str] = {source}
        queue: list[tuple[str, list[str]]] = [(source, [source])]

        for _ in range(max_depth):
            next_queue: list[tuple[str, list[str]]] = []
            for current, path in queue:
                neighbors = await asyncio.to_thread(
                    get_neighbors, current, depth=1, workspace_path=workspace
                )
                for n in neighbors:
                    nid = n.get("id", "")
                    if nid == target:
                        return {"source": source, "target": target, "path": path + [nid], "found": True}
                    if nid and nid not in visited:
                        visited.add(nid)
                        next_queue.append((nid, path + [nid]))
            queue = next_queue
            if not queue:
                break

        return {"source": source, "target": target, "path": [], "found": False}
