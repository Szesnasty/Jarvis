"""Section-type classifier for PDF section notes (step 28d).

Two-stage classification:
  Stage 1 — heuristic (pure Python, zero cost).
  Stage 2 — LLM fallback (Claude Haiku) for uncertain cases.

Public API:
  classify_section_heuristic(title, body) -> (type, confidence, signals)
  classify_section_llm(title, body, anthropic_client) -> (type, confidence)
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple

# ── Taxonomy ─────────────────────────────────────────────────────────────────

SECTION_TYPES: List[str] = [
    "requirements",
    "risks",
    "integrations",
    "security",
    "timeline",
    "pricing",
    "stakeholders",
    "open_questions",
    "technical_constraints",
    "business_goals",
    "front_matter",
    "other",
]

# ── Keyword tables ────────────────────────────────────────────────────────────
# Each entry: (keyword, weight)  — weights are additive per type.

_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "requirements": [
        ("must", 0.6), ("shall", 0.8), ("should", 0.4), ("required", 0.6),
        ("requirement", 0.8), ("wymaganie", 0.8), ("wymagania", 0.8),
        ("wymagań", 0.8), ("wymagany", 0.6), ("obowiązkowe", 0.6),
        ("musi", 0.6), ("ma zapewniać", 0.5),
    ],
    "risks": [
        ("risk", 0.7), ("threat", 0.7), ("vulnerability", 0.8), ("ryzyko", 0.8),
        ("ryzyka", 0.8), ("zagrożenie", 0.7), ("zagrożenia", 0.7),
        ("threat model", 0.9), ("attack", 0.5), ("exploit", 0.7),
        ("mitigation", 0.6), ("ryzykowne", 0.6),
    ],
    "integrations": [
        ("api", 0.5), ("webhook", 0.8), ("integration", 0.7), ("integracja", 0.8),
        ("integracje", 0.8), ("endpoint", 0.6), ("rest", 0.4), ("graphql", 0.6),
        ("connector", 0.7), ("adapter", 0.5), ("interface", 0.4),
    ],
    "security": [
        ("auth", 0.6), ("authentication", 0.8), ("authorization", 0.8),
        ("encryption", 0.8), ("access control", 0.8), ("rbac", 0.9),
        ("tls", 0.7), ("ssl", 0.6), ("jwt", 0.7), ("oauth", 0.8),
        ("password", 0.5), ("token", 0.4), ("bezpieczeństwo", 0.8),
        ("uwierzytelnienie", 0.8), ("autoryzacja", 0.8),
    ],
    "timeline": [
        ("milestone", 0.8), ("deadline", 0.8), ("phase", 0.5), ("harmonogram", 0.9),
        ("schedule", 0.7), ("sprint", 0.4), ("delivery", 0.5), ("termin", 0.7),
        ("termin oddania", 0.9), ("etap", 0.5), ("kamień milowy", 0.9),
    ],
    "pricing": [
        ("cost", 0.6), ("budget", 0.8), ("pricing", 0.9), ("wycena", 0.9),
        ("koszt", 0.8), ("budżet", 0.8), ("price", 0.7), ("fee", 0.6),
        ("invoice", 0.7), ("faktura", 0.7), ("cena", 0.7),
    ],
    "stakeholders": [
        ("stakeholder", 0.9), ("interesariusz", 0.9), ("owner", 0.5),
        ("responsible", 0.5), ("team", 0.4), ("contact", 0.4),
        ("point of contact", 0.8), ("sponsor", 0.6), ("właściciel", 0.7),
        ("odpowiedzialny", 0.7), ("zespół", 0.4),
    ],
    "open_questions": [
        ("tbd", 0.9), ("unclear", 0.7), ("to confirm", 0.9),
        ("do ustalenia", 0.9), ("do wyjaśnienia", 0.9),
        ("open question", 0.9), ("unknown", 0.6), ("pending", 0.6),
        ("otwarta kwestia", 0.9), ("do potwierdzenia", 0.9),
    ],
    "technical_constraints": [
        ("constraint", 0.8), ("limitation", 0.8), ("must support", 0.9),
        ("ograniczenie", 0.8), ("ograniczenia", 0.8), ("wymóg techniczny", 0.9),
        ("compatibility", 0.6), ("scalability", 0.6), ("performance", 0.5),
        ("infrastructure", 0.5),
    ],
    "business_goals": [
        ("objective", 0.8), ("goal", 0.7), ("kpi", 0.9), ("cel", 0.7),
        ("cele", 0.7), ("metric", 0.6), ("okr", 0.8), ("roi", 0.8),
        ("business value", 0.9), ("wartość biznesowa", 0.9), ("target", 0.5),
    ],
    "front_matter": [
        ("executive summary", 0.9), ("table of contents", 0.9),
        ("spis treści", 0.9), ("streszczenie", 0.7), ("abstract", 0.7),
        ("introduction", 0.4), ("overview", 0.4), ("scope", 0.4),
        ("preamble", 0.8),
    ],
}

# ── Heading priors ───────────────────────────────────────────────────────────
# If the heading matches a pattern, add a prior to the corresponding type.

_HEADING_PRIORS: List[Tuple[re.Pattern, str, float]] = [
    (re.compile(r"^risks?$", re.I), "risks", 0.4),
    (re.compile(r"^ryzyk[ao]?$", re.I), "risks", 0.4),
    (re.compile(r"^wymagani[ae]$", re.I), "requirements", 0.4),
    (re.compile(r"^requirements?$", re.I), "requirements", 0.4),
    (re.compile(r"^cennik$", re.I), "pricing", 0.4),
    (re.compile(r"^pricing$", re.I), "pricing", 0.4),
    (re.compile(r"^integracje$", re.I), "integrations", 0.4),
    (re.compile(r"^integrations?$", re.I), "integrations", 0.4),
    (re.compile(r"^harmonogram$", re.I), "timeline", 0.4),
    (re.compile(r"^timeline$", re.I), "timeline", 0.4),
    (re.compile(r"^schedule$", re.I), "timeline", 0.4),
    (re.compile(r"^bezpiecze[nń]stwo$", re.I), "security", 0.4),
    (re.compile(r"^security$", re.I), "security", 0.4),
    (re.compile(r"^interesariusze?$", re.I), "stakeholders", 0.4),
    (re.compile(r"^stakeholders?$", re.I), "stakeholders", 0.4),
    (re.compile(r"^(open )?questions?$", re.I), "open_questions", 0.4),
    (re.compile(r"^otwarte kwestie$", re.I), "open_questions", 0.4),
    (re.compile(r"^wstęp$", re.I), "front_matter", 0.4),
    (re.compile(r"^executive summary$", re.I), "front_matter", 0.4),
    (re.compile(r"^(project )?overview$", re.I), "front_matter", 0.3),
    (re.compile(r"^cele$", re.I), "business_goals", 0.4),
    (re.compile(r"^(business )?goals?$", re.I), "business_goals", 0.4),
    (re.compile(r"^ograniczeni[ae]$", re.I), "technical_constraints", 0.4),
    (re.compile(r"^(technical )?constraints?$", re.I), "technical_constraints", 0.4),
]

# ── Heuristic min word count to trust keyword ratio ─────────────────────────
_MIN_WORDS = 10
_CONFIDENCE_ACCEPT = 0.6
_MARGIN_ACCEPT = 0.15


def _normalize(text: str) -> str:
    """Lowercase + strip diacritics for PL–EN matching."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def classify_section_heuristic(
    title: str,
    body: str,
) -> Tuple[str, float, Dict]:
    """Stage-1 heuristic classifier.

    Returns (section_type, confidence, signals) where signals is a dict
    with raw scores per type (debug use only, not written to frontmatter).

    If confidence < _CONFIDENCE_ACCEPT or margin < _MARGIN_ACCEPT, returns
    type 'other' to trigger Stage-2.
    """
    combined = f"{title}\n{body}"
    norm = _normalize(combined)
    words = re.findall(r"\b\w+\b", norm)
    word_count = max(len(words), 1)

    # Keyword scoring — count-based, normalised by word_count
    raw_scores: Dict[str, float] = {t: 0.0 for t in SECTION_TYPES}
    for stype, kws in _KEYWORDS.items():
        for kw, weight in kws:
            norm_kw = _normalize(kw)
            occurrences = norm.count(norm_kw)
            if occurrences > 0:
                raw_scores[stype] += weight * min(occurrences, 5) / (word_count / 100 + 1)

    # Normalise to [0, 1]
    max_raw = max(raw_scores.values()) or 1.0
    scores: Dict[str, float] = {t: v / max_raw for t, v in raw_scores.items()}

    # Heading prior
    title_stripped = title.strip().lstrip("#").strip()
    for pattern, stype, prior in _HEADING_PRIORS:
        if pattern.match(title_stripped):
            scores[stype] = min(1.0, scores[stype] + prior)

    # Sort descending
    sorted_types = sorted(scores, key=lambda t: scores[t], reverse=True)
    best = sorted_types[0]
    second = sorted_types[1]
    confidence = scores[best]
    margin = scores[best] - scores[second]

    if word_count < _MIN_WORDS:
        return "other", 0.0, scores

    if confidence >= _CONFIDENCE_ACCEPT and margin >= _MARGIN_ACCEPT:
        return best, confidence, scores

    # Low confidence — fall through to LLM
    return "other", confidence, scores


async def classify_section_llm(
    title: str,
    body: str,
    anthropic_client,
) -> Tuple[str, float]:
    """Stage-2 LLM classifier using Claude Haiku.

    Sends up to 500 chars of the section head + title to the model.
    Returns (section_type, confidence).
    """
    snippet = body[:500].strip()
    types_list = ", ".join(t for t in SECTION_TYPES if t != "other")

    prompt = (
        f"You are classifying a section of a document. "
        f"Choose EXACTLY ONE label from this list: {types_list}, other.\n\n"
        f"Section heading: {title}\n"
        f"Section excerpt: {snippet}\n\n"
        f"Respond with only the label (one word or phrase from the list above, no punctuation)."
    )

    try:
        message = await anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip().lower().replace(" ", "_")
        # Map back to canonical type
        if raw in SECTION_TYPES:
            return raw, 0.75
        # Fuzzy match — accept longest prefix match
        for stype in SECTION_TYPES:
            if stype.startswith(raw) or raw.startswith(stype):
                return stype, 0.70
        return "other", 0.5
    except Exception:
        return "other", 0.0
