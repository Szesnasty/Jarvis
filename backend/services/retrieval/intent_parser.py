"""Deterministic query-intent parser for Jira-aware retrieval (step 22f).

Pattern-based — no LLM. Extracts Jira issue keys, status words, sprint
references, risk/ambiguity hints, business-area keywords, and section-type
preferences (step 28d).
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple

from services.enrichment.models import DEFAULT_BUSINESS_AREAS
from services.retrieval.intent import FacetFilter, QueryIntent

# ── Issue key ───────────────────────────────────────────────────────
ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")

# ── Status words ────────────────────────────────────────────────────
_STATUS_OPEN = {
    "open", "to do", "todo", "new",
    "otwarte", "otwarty", "otwarta", "nowe", "nowy", "nowa",
    "do zrobienia", "backlog",
}
_STATUS_IN_PROGRESS = {
    "in progress", "in-progress", "doing",
    "w trakcie", "w toku", "w realizacji", "realizowane",
}
_STATUS_DONE = {
    "done", "closed", "resolved", "finished",
    "zamknięte", "zamknięty", "zamknięta",
    "zakończone", "zakończony", "zakończona",
    "zrobione", "zrobiony", "zrobiona",
    "rozwiązane", "rozwiązany", "rozwiązana",
}

_STATUS_MAP = {
    **{w: "To Do" for w in _STATUS_OPEN},
    **{w: "In Progress" for w in _STATUS_IN_PROGRESS},
    **{w: "Done" for w in _STATUS_DONE},
}

# ── Sprint references ──────────────────────────────────────────────
_SPRINT_CURRENT_RE = re.compile(
    r"\b(this sprint|current sprint|"
    r"aktualn[a-z]* (?:sprint|sprincie|sprintach|sprintu|sprinty|sprintem)|"
    r"bieżąc[a-z]* (?:sprint|sprincie|sprintach|sprintu|sprinty|sprintem)|"
    r"w (?:tym|aktualnym|bieżącym) sprincie)\b",
    re.IGNORECASE,
)

# ── Issue-intent words ─────────────────────────────────────────────
_ISSUE_WORDS: Set[str] = {
    "task", "tasks", "ticket", "tickets", "issue", "issues",
    "bug", "bugs", "story", "stories", "epic", "epics",
    "sprint", "sprints", "blocker", "blockers",
    # Polish variants (nouns + common declensions).
    "zadanie", "zadania", "zadań", "zadaniom",
    "zgłoszenie", "zgłoszenia", "zgłoszeń",
    "błąd", "błędy", "błędów",
    "historia", "historie", "historii",
    "sprincie", "sprintach", "sprintu",
    "blokery", "blokerów",
    "tiket", "tikety",
    "jira",
}

# ── Risk / ambiguity hints ─────────────────────────────────────────
_RISK_WORDS: Set[str] = {
    "risky", "risk", "critical", "blocker", "blockers", "high-risk",
    # Polish variants.
    "ryzyko", "ryzyka", "ryzykowne", "ryzykowny", "ryzykowna",
    "krytyczne", "krytyczny", "krytyczna",
    "zagrożenie", "zagrożenia", "zagrożeń",
    "zagrożone", "zagrożony", "zagrożona",
    "blokujące", "blokujący", "blokująca", "blokuje",
    "blokowane", "blokowany", "blokowana",
}
_AMBIGUITY_WORDS: Set[str] = {
    "unclear", "uncertain", "ambiguous", "vague",
    # Polish variants.
    "niejasne", "niejasny", "niejasna",
    "niepewne", "niepewny", "niepewna",
    "niedoprecyzowane", "niedoprecyzowany",
    "dwuznaczne", "dwuznaczny",
}

# ── Open-only hints ────────────────────────────────────────────────
_OPEN_HINTS_RE = re.compile(
    r"\b(what('s| is) (open|left|remaining|to do)|"
    r"co jest otwarte|co zostało(?: do zrobienia)?|"
    r"co mamy otwarte|co jest w toku)\b",
    re.IGNORECASE,
)

# ── Blocking / dependency queries ──────────────────────────────────
_BLOCKS_RE = re.compile(
    r"\b(what blocks|blocked by|depends on|blocking|"
    r"blokuje|blokuj[aą]|blokowane przez|blokowan[yaei]\s+przez|"
    r"zależy od|zależne od|zależne)\b",
    re.IGNORECASE,
)

# ── Section-type intent (step 28d) ────────────────────────────────
# Maps section_type label → list of (pattern, weight) trigger phrases.
# First match with total weight ≥ 1.0 is accepted.
_SECTION_TYPE_PATTERNS: List[Tuple[str, List[Tuple[re.Pattern, float]]]] = [
    ("risks", [
        (re.compile(r"\b(risk|risks|ryzyk[ao]|zagrożeni[ae]|threat|threats|vulnerability|vulnerabilities)\b", re.I), 1.0),
        (re.compile(r"\bwhat (risks?|threats?)\b", re.I), 1.0),
        (re.compile(r"\bjakie ryzyk[ao]\b", re.I), 1.0),
    ]),
    ("requirements", [
        (re.compile(r"\b(requirements?|wymagani[ae]|wymagań)\b", re.I), 1.0),
        (re.compile(r"\bwhat (does|do) .*? (require|need|expect)\b", re.I), 1.0),
        (re.compile(r"\bjakie wymagania\b", re.I), 1.0),
        (re.compile(r"\bco (klient|zamawiający) (wymaga|oczekuje)\b", re.I), 1.0),
    ]),
    ("integrations", [
        (re.compile(r"\b(integrations?|integracje|integracja)\b", re.I), 1.0),
        (re.compile(r"\bwhat (api|apis|webhooks?|integrations?)\b", re.I), 1.0),
        (re.compile(r"\bco dokument mówi o integracjach\b", re.I), 1.0),
    ]),
    ("timeline", [
        (re.compile(r"\b(timeline|milestones?|deadlines?|harmonogram|terminy?|etapy)\b", re.I), 1.0),
        (re.compile(r"\bwhat (is the timeline|are the (?:milestones?|deadlines?))\b", re.I), 1.0),
    ]),
    ("pricing", [
        (re.compile(r"\b(pricing|costs?|budget|wycena|koszt[uy]?|budżet)\b", re.I), 1.0),
        (re.compile(r"\bhow much\b", re.I), 1.0),
        (re.compile(r"\bile to kosztuje\b", re.I), 1.0),
    ]),
    ("security", [
        (re.compile(r"\b(security|bezpieczeństwo|auth(?:entication|orization)?|encryption|rbac|access control)\b", re.I), 1.0),
    ]),
    ("stakeholders", [
        (re.compile(r"\b(stakeholders?|interesariusze?|właściciel|owner)\b", re.I), 1.0),
        (re.compile(r"\bwho (is responsible|owns|manages)\b", re.I), 1.0),
    ]),
    ("open_questions", [
        (re.compile(r"\b(tbd|open (?:questions?|issues?)|do ustalenia|niejasności)\b", re.I), 1.0),
        (re.compile(r"\bwhat (is|are) (unclear|unknown|pending|tbd)\b", re.I), 1.0),
    ]),
    ("technical_constraints", [
        (re.compile(r"\b(constraints?|limitations?|ograniczeni[ae]|wymogi techniczne)\b", re.I), 1.0),
    ]),
    ("business_goals", [
        (re.compile(r"\b(goals?|objectives?|kpis?|cele|cel|okrs?)\b", re.I), 1.0),
        (re.compile(r"\bwhat (are|is) the (goals?|objectives?|kpis?)\b", re.I), 1.0),
        (re.compile(r"\bjakie (są )?(cele|kpis?)\b", re.I), 1.0),
    ]),
]

# Imported lazily to avoid circular import at module level
_Tuple = None  # placeholder to satisfy type-checkers below


def _detect_preferred_section_types(text: str) -> List[str]:
    """Return section types signalled by the query (step 28d).

    Iterates pattern groups in order; first matching type added to result.
    Multiple types can match (e.g. "security requirements").
    """
    matched: List[str] = []
    for stype, patterns in _SECTION_TYPE_PATTERNS:
        for pattern, _w in patterns:
            if pattern.search(text):
                matched.append(stype)
                break  # only count each type once
    return matched


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
        r"(?:assigned to|assignee:?|przypisane do)\s+(\S+)",
        text, re.IGNORECASE,
    )
    if assignee_match:
        assignee_filter = assignee_match.group(1)

    # --- Project key from issue keys ---
    project_keys: Optional[List[str]] = None
    if keys:
        pks = list(dict.fromkeys(k.split("-")[0] for k in keys))
        project_keys = pks if pks else None

    # --- Section-type preference (step 28d) ---
    preferred_section_types = _detect_preferred_section_types(text)

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
        preferred_section_types=preferred_section_types,
    )
