"""Query intent and facet filter data models for Jira-aware retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FacetFilter:
    """Structured facets extracted from a query or supplied by the UI."""

    status_category: Optional[List[str]] = None
    sprint_state: Optional[List[str]] = None
    sprint_name: Optional[List[str]] = None
    assignee: Optional[List[str]] = None
    project_key: Optional[List[str]] = None
    business_area: Optional[List[str]] = None
    risk_level: Optional[List[str]] = None
    ambiguity_level: Optional[List[str]] = None
    work_type: Optional[List[str]] = None

    @property
    def is_empty(self) -> bool:
        return all(
            getattr(self, f.name) is None
            for f in self.__dataclass_fields__.values()
        )


@dataclass
class QueryIntent:
    """Parsed query intent — deterministic, no LLM."""

    text: str
    facets: FacetFilter = field(default_factory=FacetFilter)
    wants_issues_only: bool = False
    wants_open_only: bool = False
    sprint_filter: Optional[str] = None
    assignee_filter: Optional[str] = None
    business_area_hint: Optional[str] = None
    risk_hint: Optional[str] = None
    keys_in_query: List[str] = field(default_factory=list)

    @property
    def has_jira_signals(self) -> bool:
        """True when the query has any Jira-related signal."""
        return bool(
            self.keys_in_query
            or self.wants_issues_only
            or self.wants_open_only
            or self.sprint_filter
            or self.assignee_filter
            or self.business_area_hint
            or self.risk_hint
            or not self.facets.is_empty
        )
