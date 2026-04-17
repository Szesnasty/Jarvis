"""Types, enums and payload schema for enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator

SUBJECT_JIRA = "jira_issue"
SUBJECT_NOTE = "note"

WORK_TYPES = {
    "bug",
    "feature",
    "refactor",
    "research",
    "ops",
    "blocker",
    "maintenance",
    "unknown",
}
EXECUTION_TYPES = {
    "implementation",
    "decision",
    "investigation",
    "dependency",
    "follow_up",
    "unknown",
}
RISK_LEVELS = {"low", "medium", "high"}
AMBIGUITY_LEVELS = {"clear", "partial", "unclear"}

DEFAULT_BUSINESS_AREAS = [
    "onboarding",
    "billing",
    "auth",
    "analytics",
    "growth",
    "infra",
    "support",
    "unknown",
]

PROMPT_VERSION = 2
QUEUE_POLL_SLEEP_S = 0.5
DEFAULT_WORKER_CONCURRENCY = 2


@dataclass
class QueueItem:
    id: int
    subject_type: str
    subject_id: str
    content_hash: str


class EnrichmentPayload(BaseModel):
    summary: str = Field(min_length=1)
    actionable_next_step: str = Field(min_length=1)
    work_type: str
    business_area: str
    execution_type: str
    risk_level: str
    ambiguity_level: str
    hidden_concerns: list[str] = Field(default_factory=list)
    likely_related_issue_keys: list[str] = Field(default_factory=list)
    likely_related_note_paths: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("keywords")
    @classmethod
    def _validate_keywords(cls, value: list[str]) -> list[str]:
        clean = [str(v).strip() for v in value if str(v).strip()]
        if len(clean) < 3:
            raise ValueError("keywords must have at least 3 values")
        return clean


def coerce_enum(value: Any, allowed: set[str], fallback: str = "unknown") -> tuple[str, bool]:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    if normalized in allowed:
        return normalized, False
    return fallback, True
