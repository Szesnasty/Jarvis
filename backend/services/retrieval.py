from typing import Dict, List, Optional

from services import graph_service, memory_service


def _extract_query_entities(query: str, graph: graph_service.Graph) -> List[str]:
    """Match query tokens against known graph node labels."""
    query_lower = query.lower()
    matches = []
    for node in graph.nodes.values():
        if node.type in ("person", "tag", "area"):
            if node.label.lower() in query_lower:
                matches.append(node.id)
    return matches


def _shortest_weighted_path(
    graph: graph_service.Graph,
    start: str,
    end: str,
    max_depth: int = 3,
) -> Optional[float]:
    """BFS-based shortest weighted path distance between two nodes."""
    if start == end:
        return 0.0
    if start not in graph.nodes or end not in graph.nodes:
        return None

    visited = {start}
    frontier = {start}
    total_cost = 0.0

    for _ in range(max_depth):
        next_frontier = set()
        min_step_cost = float("inf")
        for edge in graph.edges:
            step_weight = 1.0 / (edge.weight + 0.01)
            if edge.source in frontier and edge.target not in visited:
                next_frontier.add(edge.target)
                min_step_cost = min(min_step_cost, step_weight)
                if edge.target == end:
                    return total_cost + step_weight
            if edge.target in frontier and edge.source not in visited:
                next_frontier.add(edge.source)
                min_step_cost = min(min_step_cost, step_weight)
                if edge.source == end:
                    return total_cost + step_weight
        if not next_frontier:
            break
        visited.update(next_frontier)
        frontier = next_frontier
        total_cost += min_step_cost if min_step_cost != float("inf") else 1.0

    return None


def _score_by_path(
    graph: graph_service.Graph,
    anchor_nodes: List[str],
    candidate_id: str,
    max_depth: int = 3,
) -> float:
    """Score a candidate by shortest weighted paths to anchor nodes."""
    total = 0.0
    for anchor in anchor_nodes:
        dist = _shortest_weighted_path(graph, candidate_id, anchor, max_depth)
        if dist is not None:
            total += 1.0 / (1.0 + dist)
    return total


async def retrieve(
    query: str,
    limit: int = 5,
    workspace_path=None,
) -> List[Dict]:
    """Weighted hybrid retrieval: FTS + graph scoring + cluster dedup."""
    if not query or not query.strip():
        return []

    # 1. FTS search (get more candidates than needed)
    candidates = await memory_service.list_notes(
        search=query,
        limit=limit * 3,
        workspace_path=workspace_path,
    )

    # 2. Load graph for scoring
    graph = graph_service.load_graph(workspace_path)
    if not graph:
        return candidates[:limit]

    # 3. Extract query entities for path scoring
    anchors = _extract_query_entities(query, graph)
    use_path_scoring = len(anchors) > 0

    # 4. Score each candidate using graph neighborhood
    scored = []
    fts_node_ids = {f"note:{c['path']}" for c in candidates}

    for i, candidate in enumerate(candidates):
        node_id = f"note:{candidate['path']}"
        fts_rank = 1.0 / (i + 1)

        # Graph score: weighted sum of edges to other FTS hits
        graph_score = 0.0
        if node_id in graph.nodes:
            for edge in graph.edges:
                if edge.source == node_id and edge.target in fts_node_ids:
                    graph_score += edge.weight
                elif edge.target == node_id and edge.source in fts_node_ids:
                    graph_score += edge.weight

            # Convergence bonus: node connects to 3+ FTS hits
            neighbor_ids = {e.target for e in graph.edges if e.source == node_id}
            neighbor_ids |= {e.source for e in graph.edges if e.target == node_id}
            overlap = len(neighbor_ids & fts_node_ids)
            if overlap >= 3:
                graph_score += 0.3

        # Path scoring if anchors found
        path_score = 0.0
        if use_path_scoring and node_id in graph.nodes:
            path_score = _score_by_path(graph, anchors, node_id)

        if use_path_scoring:
            final_score = fts_rank * 0.4 + graph_score * 0.3 + path_score * 0.3
        else:
            final_score = fts_rank * 0.6 + graph_score * 0.4

        scored.append({**candidate, "_score": final_score, "_node_id": node_id})

    # 5. Sort by final score
    scored.sort(key=lambda x: x["_score"], reverse=True)

    # 6. Cluster dedup: avoid returning 3+ notes from same folder
    seen_folders: Dict[str, int] = {}
    result = []
    for item in scored:
        folder = item.get("folder", "")
        if folder and seen_folders.get(folder, 0) >= 2:
            continue
        seen_folders[folder] = seen_folders.get(folder, 0) + 1
        result.append(item)
        if len(result) >= limit:
            break

    # Clean internal fields
    for r in result:
        r.pop("_score", None)
        r.pop("_node_id", None)

    return result
