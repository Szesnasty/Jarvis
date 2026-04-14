import re
from dataclasses import dataclass
from typing import List


@dataclass
class ExtractedEntity:
    text: str
    type: str       # "person" | "date" | "project"
    confidence: float  # 0.0 - 1.0


# --- Person detection ---
_PERSON_RE = re.compile(
    r"(?:(?:with|from|by|to|for|and|met|called|emailed|told|asked)\s+)"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
)

_STANDALONE_NAME_RE = re.compile(
    r"\b((?:Dr|Mr|Mrs|Ms|Prof)\.?\s+)?([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?)\b"
)

# --- Date detection ---
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\b", re.I),
    re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b", re.I),
    re.compile(r"\b((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b", re.I),
    re.compile(r"\b(yesterday|today|tomorrow|last week|next week|this week)\b", re.I),
]

# --- Project detection ---
_PROJECT_RE = re.compile(r"(?:project|initiative|program)[:\s]+([A-Z][\w\s-]{2,30}?)(?:[,.\n]|$)", re.I)

# Common false positives to skip
_SKIP_NAMES = frozenset({
    "The", "This", "That", "There", "These", "Those", "What", "When",
    "Where", "Which", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday", "January", "February", "March",
    "April", "May", "June", "July", "August", "September", "October",
    "November", "December", "New York", "United States", "San Francisco",
    "HTTP", "HTML", "JSON", "YAML", "TODO", "NOTE", "FIXME",
})

_SKIP_ACRONYMS = frozenset({
    "AI", "ML", "US", "UK", "EU", "IT", "HR", "PM", "CEO", "CTO",
    "API", "URL", "PDF", "CSV", "SQL", "HTTP", "HTML", "JSON",
    "TODO", "NOTE", "FIXME", "NASA", "FAQ",
})


def extract_entities(text: str, existing_people: List[str] = None) -> List[ExtractedEntity]:
    """Extract entities from note text using regex heuristics.

    existing_people: known person labels from graph, used to boost confidence.
    """
    entities: List[ExtractedEntity] = []
    existing_set = {p.lower() for p in (existing_people or [])}

    # People — standalone names
    for match in _STANDALONE_NAME_RE.finditer(text):
        name = match.group(2).strip()
        if name in _SKIP_NAMES or len(name) < 4:
            continue
        confidence = 0.7 if name.lower() in existing_set else 0.4
        entities.append(ExtractedEntity(text=name, type="person", confidence=confidence))

    # People — contextual names (after "with", "from", etc.)
    for match in _PERSON_RE.finditer(text):
        name = match.group(1).strip()
        if name in _SKIP_NAMES or len(name) < 4:
            continue
        confidence = 0.8 if name.lower() in existing_set else 0.5
        entities.append(ExtractedEntity(text=name, type="person", confidence=confidence))

    # Dates
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            entities.append(ExtractedEntity(
                text=match.group(1) if match.lastindex else match.group(0),
                type="date",
                confidence=0.9,
            ))

    # Projects
    for match in _PROJECT_RE.finditer(text):
        name = match.group(1).strip()
        if len(name) < 3:
            continue
        entities.append(ExtractedEntity(text=name, type="project", confidence=0.6))

    # Deduplicate by (text.lower(), type), keeping highest confidence
    seen: dict = {}
    for e in entities:
        key = (e.text.lower(), e.type)
        if key not in seen or e.confidence > seen[key].confidence:
            seen[key] = e

    return list(seen.values())
