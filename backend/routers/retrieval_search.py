"""Retrieval search endpoint (step 22f).

POST /api/retrieval/search — run hybrid retrieval with optional
facet filtering and intent parsing.
"""

from fastapi import APIRouter

from models.schemas import (
    FacetFilterRequest,
    IntentResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from services.retrieval import retrieve_with_intent
from services.retrieval.intent import FacetFilter

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


def _facet_request_to_filter(req: FacetFilterRequest | None) -> FacetFilter | None:
    """Convert API schema to internal dataclass."""
    if not req:
        return None
    return FacetFilter(
        status_category=req.status_category,
        sprint_state=req.sprint_state,
        sprint_name=req.sprint_name,
        assignee=req.assignee,
        project_key=req.project_key,
        business_area=req.business_area,
        risk_level=req.risk_level,
        ambiguity_level=req.ambiguity_level,
        work_type=req.work_type,
    )


@router.post("/search", response_model=RetrievalSearchResponse)
async def search(body: RetrievalSearchRequest):
    """Run hybrid retrieval with intent parsing and optional facets."""
    facets = _facet_request_to_filter(body.facets)

    intent, results = await retrieve_with_intent(
        body.query,
        limit=body.top_k,
        facets_override=facets,
    )

    return RetrievalSearchResponse(
        results=results,
        intent=IntentResponse(
            text=intent.text,
            wants_issues_only=intent.wants_issues_only,
            wants_open_only=intent.wants_open_only,
            sprint_filter=intent.sprint_filter,
            assignee_filter=intent.assignee_filter,
            business_area_hint=intent.business_area_hint,
            risk_hint=intent.risk_hint,
            keys_in_query=intent.keys_in_query,
            has_jira_signals=intent.has_jira_signals,
        ),
        result_count=len(results),
    )
