"""Deterministic query-intent parser for Jira-aware retrieval (step 22f).

Pattern-based — no LLM. Extracts Jira issue keys, status words, sprint
references, risk/ambiguity hints, and business-area keywords.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set

from services.enrichment.models import DEFAULT_BUSINESS_AREAS
from services.retrieval.intent import FacetFilter, QueryIntent

# ── Issue key ───────────────────────────────────────────────────────
ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")

# ── Status words ────────────────────────────────────────────────────
_STATUS_OPEN = {"open", "to do", "todo", "new", "otwarte", "nowe"}
_STATUS_IN_PROGRESS = {"in progress", "in-progress", "doing", "w trakcie", "w toku"}
_STATUS_DONE = {"done", "closed", "resolved", "finished", "zamknięte", "zakończone", "zrobione"}

_STATUS_MAP = {
    **{w: "To Do" for w in _STATUS_OPEN},
    **{w: "In Progress" for w in _STATUS_IN_PROGRESS},
    **{w: "Done" for w in _STATUS_DONE},
}

# ── Sprint references ──────────────────────────────────────────────
_SPRINT_CURRENT_RE = re.compile(
    r"\b(this sprint|current sprint|aktualn[yiae] sprint|bieżąc[yiae] sprint)\b",
    re.IGNORECASE,
)

# ── Issue-intent words ─────────────────────────────────────────────
_ISSUE_WORDS: Set[str] = {
    "task", "tasks", "ticket", "tickets", "issue", "issues",
    "bug", "bugs", "story", "stories", "epic", "epics",
    "sprint", "blocker", "blockers",
    "zadanie", "zadania", "błąd", "błędy", "historia", "historie",
    "jira",
}

# ── Risk / ambiguity hints ─────────────────────────────────────────
_RISK_WORDS: Set[str] = {
    "risky", "risk", "critical", "blocker", "blockers", "high-risk",
    "ryzykowne", "krytyczne", "blokujące",
}
_AMBIGUITY_WORDS: Set[str] = {
    "unclear", "uncertain", "ambiguous", "vague",
    "niejasne", "niepewne",
}

# ── Open-only hints ────────────────────────────────────────────────
_OPEN_HINTS_RE = re.compile(
    r"\b(what('s| is) (open|left|remaining|to do)|"
    r"co jest otwarte|co zostało)\b",
    re.IGNORECASE,
)

# ── Blocking / dependency queries ──────────────────────────────────
_BLOCKS_RE = re.compile(
    r"\b(what blocks|blocked by|depends on|blocking|blokuje|blokowane przez|zależy od)\b",
    re.IGNORECASE,
)


def parse_intent(query: str) -> QueryIntent:
    """Parse a user query into a structured QueryIntent."""
    text = query.strip()
    text_lower = text.lower()
    words = set(re.findall(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", text_lower))

    # --- Issue keys ---
    keys: List[str] = ISSUE_KEY_RE.findall(text)

    # --- Wants issues only ---
    wants_issues = bool(keys) or bool(words & _ISSUE_WORDS) or bool(_BLOCKS_RE.search(text))

    # --- Status filter ---
    status_categories: List[str] = []
    for pattern, category in _STATUS_MAP.items():
        if pattern in text_lower:
            if category not in status_categories:
                status_categories.append(category)

    # --- Open only ---
    wants_open = bool(_OPEN_HINTS_RE.search(text))
    if wants_open and "To Do" not in status_categories and "In Progress" not in status_categories:
        status_categories.extend(["To Do", "In Progress"])

    # --- Sprint ---
    sprint_filter: Optional[str] = None
    sprint_state: Optional[List[str]] = None
    if _SPRINT_CURRENT_RE.search(text):
        sprint_filter = "active"
        sprint_state = ["active"]
        wants_issues = True

    # --- Business area ---
    business_area_hint: Optional[str] = None
    for area in DEFAULT_BUSINESS_AREAS:
        if area != "unknown" and area in text_lower:
            business_area_hint = area
            break

    # --- Risk hint ---
    risk_hint: Optional[str] = None
    if words & _RISK_WORDS:
        risk_hint = "high-risk"
    elif words & _AMBIGUITY_WORDS:
        risk_hint = "unclear"

    # --- Assignee (simple "assigned to X" pattern) ---
    assignee_filter: Optional[str] = None
    assignee_match = re.search(
        r"(?:assigned to|assignee[: ]+|przypisane do)\s+(\S+)",
        text, re.IGNORECASE,
    )
    if assignee_match:
        assignee_filter = assignee_match.group(1)

    # --- Project key from issue keys ---
    project_keys: Optional[List[str]] = None
    if keys:
        pks = list(dict.fromkeys(k.split("-")[0] for k in keys))
        project_keys = pks if pks else None

    # --- Build facet filter ---
    facets = FacetFilter(
        status_category=status_categories or None,
        sprint_state=sprint_state,
        assignee=[assignee_filter] if assignee_filter else None,
        project_key=project_keys,
        business_area=[business_area_hint] if business_area_hint else None,
        risk_level=["high"] if risk_hint == "high-risk" else None,
        ambiguity_level=["unclear"] if risk_hint == "unclear" else None,
    )

    return QueryIntent(
        text=text,
        facets=facets,
        wants_issues_only=wants_issues,
        wants_open_only=wants_open,
        sprint_filter=sprint_filter,
        assignee_filter=assignee_filter,
        business_area_hint=business_area_hint,
        risk_hint=risk_hint,
        keys_in_query=keys,
    )
