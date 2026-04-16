"""Knowledge graph service — modular package.

Re-exports all public symbols so existing imports like
``from services.graph_service import rebuild_graph`` continue to work.
"""

# --- Models ---
from services.graph_service.models import (  # noqa: F401
    Edge,
    Graph,
    Node,
    apply_edge_weights,
    compute_tag_idf,
    extract_wiki_links,
)

# Backwards compat alias
_apply_edge_weights = apply_edge_weights

# --- Similarity ---
from services.graph_service.similarity import (  # noqa: F401
    compute_similarity_edges as _compute_similarity_edges,
    compute_temporal_edges as _compute_temporal_edges,
    prune_overloaded_tags as _prune_overloaded_tags,
    _compute_chunk_similarity_edges,
    _compute_embedding_similarity_edges,
    _compute_keyword_similarity_edges,
)

# --- Builder ---
from services.graph_service.builder import (  # noqa: F401
    invalidate_cache,
    load_graph,
    rebuild_graph,
    _graph_cache,
)

# --- Queries ---
from services.graph_service.queries import (  # noqa: F401
    add_conversation_to_graph,
    find_orphans,
    get_neighbors,
    get_node_detail,
    ingest_note,
    query_entity,
)
