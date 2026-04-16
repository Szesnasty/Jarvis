import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    text: str
    type: str       # "person" | "date" | "project" | "organization"
    confidence: float  # 0.0 - 1.0


# ---------------------------------------------------------------------------
# spaCy NER (primary) — loaded lazily
# ---------------------------------------------------------------------------
_nlp_pl = None
_nlp_en = None
_spacy_available: Optional[bool] = None


def _load_spacy():
    """Lazily load spaCy models. Returns True if available."""
    global _nlp_pl, _nlp_en, _spacy_available
    if _spacy_available is not None:
        return _spacy_available
    try:
        import spacy
        _nlp_pl = spacy.load("pl_core_news_sm")
        try:
            _nlp_en = spacy.load("en_core_web_sm")
        except OSError:
            logger.debug("en_core_web_sm not available, using Polish model only")
        _spacy_available = True
    except (ImportError, OSError) as exc:
        logger.debug("spaCy not available, falling back to regex: %s", exc)
        _spacy_available = False
    return _spacy_available


# spaCy entity label → our entity type
_SPACY_LABEL_MAP = {
    # Polish model labels
    "persName": "person",
    "orgName": "organization",
    "placeName": "place",
    "date": "date",
    # English model labels
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "place",
    "DATE": "date",
}

# Known false positives from spaCy
_SPACY_SKIP = frozenset({
    # Tech / product names
    "Backend", "Frontend", "Pythonie", "Vitest", "Claude", "Jarvis",
    "Llama", "FastAPI", "Nuxt", "SQLite", "Obsidian", "Whisper",
    "Docker", "Kubernetes", "React", "Vue", "TypeScript",
    # Polish morphological false positives
    "skiej",
})

# Common words/months that spaCy small model misclassifies as persName
_POLISH_NON_PERSON = frozenset({
    # Polish months
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
    # English months
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # English days
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    # Common nouns often misclassified
    "melatonina", "postępy", "przerobić", "loty", "urlop", "budżet",
    "sprint", "raport", "spotkanie", "podsumowanie", "notatki", "plan",
    "praca", "projekt", "zadanie", "trening", "dieta", "suplementy",
    "magnez", "witamina", "omega", "cynk", "kreatyna", "kolagen",
    "ashwagandha", "kurkuma", "probiotyk",
})

# Words that are definitely not parts of person names — used to reject
# multi-word entities containing them (e.g. "Review PR", "Deploy App")
_NOT_NAME_WORDS = frozenset({
    # English tech/work verbs that PL model sometimes captures
    "review", "update", "deploy", "push", "pull", "merge", "release",
    "install", "build", "test", "run", "check", "fix", "create",
    "delete", "send", "upload", "download", "sync", "backup",
    # Common abbreviations / acronyms
    "pr", "ci", "cd", "api", "url", "sql", "css", "html", "http",
    "qa", "ui", "ux", "ml", "ai", "db", "cli", "sdk", "jwt",
    "mvp", "crm", "erp", "kpi", "roi", "seo",
    # Role/title words that appear in compound terms (not person names)
    "coach", "manager", "guide", "assistant", "planner", "tracker",
})


def _lemmatize_name(ent) -> str:
    """Use spaCy lemmatizer to normalize a Polish name to base (nominative) form.

    E.g. "Michałem Kowalskim" → "Michał Kowalski" (via token lemmas).
    Falls back to original text when the lemmatizer produces garbage
    (e.g. foreign names like "Will" → "willć").
    """
    parts = []
    for tok in ent:
        lemma = tok.lemma_
        # If lemma is lowercase but original is uppercase, title-case the lemma
        if lemma[0].islower() and tok.text[0].isupper():
            lemma = lemma.title()
        # If lemma equals the original lowercase (lemmatizer didn't change it),
        # keep the original text with its original casing
        if lemma.lower() == tok.text.lower():
            parts.append(tok.text)
        # Guard: reject lemmas that add new characters not in the original.
        # Polish declension only changes suffixes (Michał→Michałem),
        # so a valid lemma should only use chars from the original.
        # E.g. "Will" → "willć" adds 'ć' → reject and keep "Will".
        elif set(lemma.lower()) - set(tok.text.lower()):
            parts.append(tok.text)
        else:
            parts.append(lemma)
    return " ".join(parts)


def _fuzzy_match_existing(name: str, existing_set: set[str]) -> Optional[str]:
    """Check if a name fuzzy-matches any known person.

    Uses simple substring/stem matching for Polish declined forms.
    E.g. "Adamem Nowakiem" should match "Adam Nowak".
    Returns the matched canonical name from existing_set, or None.
    When multiple candidates match, returns the best one (most overlap).
    """
    name_lower = name.lower()
    for known in existing_set:
        # Exact match — immediate return
        if name_lower == known:
            return known

    name_parts = name_lower.split()
    best_match = None
    best_score = 0

    for known in existing_set:
        known_parts = known.split()

        # Multi-word matching: each part of known name must stem-match a part
        if len(known_parts) >= 2 and len(name_parts) >= 2:
            matches = 0
            overlap = 0
            for kp in known_parts:
                for np_ in name_parts:
                    if _stem_match(kp, np_):
                        matches += 1
                        overlap += _char_overlap(kp, np_)
                        break
            if matches == len(known_parts) and overlap > best_score:
                best_score = overlap
                best_match = known

        # Single-word matching: declined first name ↔ known person
        # E.g. "Ani" ↔ "ania krawczyk", "Adamem" ↔ "adam nowak"
        # Returns full canonical name for graph dedup
        if len(name_parts) == 1:
            for kp in known_parts:
                if _stem_match(name_lower, kp):
                    overlap = _char_overlap(name_lower, kp)
                    if overlap > best_score:
                        best_score = overlap
                        best_match = known

    return best_match


def _char_overlap(a: str, b: str) -> float:
    """Score the similarity between two words for fuzzy matching.

    Uses ratio of shared characters from the start, weighted by
    total character coverage of the shorter word.
    E.g. "marek" vs "marka" = high (shared stem "mar" + "k"),
         "marek" vs "martin" = lower (only "mar" shared).
    """
    if not a or not b:
        return 0.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    # Count matching chars at each position
    positional = sum(1 for x, y in zip(shorter, longer) if x == y)
    # Also check if shorter is mostly contained in longer (handles reordered chars)
    char_count = sum(1 for c in set(shorter) if c in longer)
    # Combined score favoring positional match
    return positional + char_count * 0.3


def _stem_match(a: str, b: str) -> bool:
    """Check if two words share a common Polish name stem.

    Handles Polish declension patterns including fleeting vowels
    (e.g. Marek→Markowi, Tomek→Tomkiem) and short name suffixes
    (e.g. Ewa→Ewy, Ola→Olą).
    """
    min_len = min(len(a), len(b))
    max_len = max(len(a), len(b))
    if min_len < 2:
        return False
    # Length ratio guard: avoid matching unrelated words
    if max_len > min_len * 2 + 1:
        return False

    # Very short words (2-3 chars): match first 2 chars
    # e.g. "ewa"↔"ewy", "ola"↔"olą", "ani"↔"ania"
    if min_len <= 3:
        return a[:2] == b[:2]

    # Medium words (4-5 chars): match first 3 chars
    # e.g. "marek"↔"markowi" (mar=mar), "tomek"↔"tomkiem" (tom=tom)
    # "adam"↔"adamem" (ada=ada), "ania"↔"anią" (ani=ani)
    if min_len <= 5:
        return a[:3] == b[:3]

    # Longer words (6+ chars): match first 4 chars
    # e.g. "kowalski"↔"kowalskiego", "wiśniewski"↔"wiśniewskiemu"
    return a[:4] == b[:4]


def _extract_with_spacy(text: str, existing_people: List[str]) -> List[ExtractedEntity]:
    """Extract person/org entities using spaCy NER."""
    existing_set = {p.lower() for p in existing_people}
    entities: List[ExtractedEntity] = []

    # Use Polish model as primary (works well on both PL and mixed PL/EN text)
    doc = _nlp_pl(text)
    for ent in doc.ents:
        etype = _SPACY_LABEL_MAP.get(ent.label_)
        if etype not in ("person", "organization"):
            continue
        name = ent.text.strip()

        # --- Filters ---
        # Reject entities with newlines/tabs (multi-line junk)
        if "\n" in name or "\t" in name:
            continue
        # Reject entities containing " - " (merged junk like "Adamem - fundraising")
        if " - " in name:
            continue
        if len(name) < 2 or name in _SPACY_SKIP:
            continue
        # Check lowercase form against known non-person words
        if name.lower() in _POLISH_NON_PERSON:
            continue
        # Reject multi-word entities containing tech/work terms
        if any(w.lower() in _NOT_NAME_WORDS for w in name.split()):
            continue

        # --- Lemmatization: normalize declined Polish names ---
        lemma_name = _lemmatize_name(ent)

        is_single_word = " " not in name

        if etype == "person":
            # Check both raw and lemmatized forms against existing people
            matched_canonical = (
                name.lower() if name.lower() in existing_set
                else lemma_name.lower() if lemma_name.lower() in existing_set
                else _fuzzy_match_existing(name, existing_set)
                or _fuzzy_match_existing(lemma_name, existing_set)
            )

            if matched_canonical:
                confidence = 0.85
                # Use canonical form from existing_people (preserving original casing)
                for ep in existing_people:
                    if ep.lower() == matched_canonical:
                        name = ep
                        break
            elif is_single_word:
                # Single-word persons are unreliable unless already known
                confidence = 0.35
            else:
                confidence = 0.6
                # For unknown multi-word names, still prefer lemmatized form
                if lemma_name != name:
                    name = lemma_name
        else:
            confidence = 0.5

        entities.append(ExtractedEntity(text=name, type=etype, confidence=confidence))

    # If English model is available, run it to catch English-specific entities missed by PL model
    # EN model on Polish text is very noisy — only accept clear proper-name patterns
    if _nlp_en is not None:
        seen_texts = {e.text.lower() for e in entities}
        doc_en = _nlp_en(text)
        for ent in doc_en.ents:
            etype = _SPACY_LABEL_MAP.get(ent.label_)
            if etype not in ("person", "organization"):
                continue
            name = ent.text.strip()
            # Apply same filters as Polish model
            if "\n" in name or "\t" in name or " - " in name:
                continue
            if len(name) < 2 or name in _SPACY_SKIP:
                continue
            if name.lower() in _POLISH_NON_PERSON:
                continue
            if any(w.lower() in _NOT_NAME_WORDS for w in name.split()):
                continue
            if name.lower() in seen_texts:
                continue
            # Also skip if fuzzy-matches an entity already found by PL model
            if _fuzzy_match_existing(name, seen_texts):
                continue

            # Strict proper-name filter for EN model results:
            # Each word must start with uppercase (rejects Polish phrases
            # that EN model misclassifies as entities)
            words = name.split()
            if not all(w[0].isupper() for w in words if len(w) > 0):
                continue
            # Reject entities with special characters (⭐, emoji, etc.)
            if not all(c.isalpha() or c in " .'-" for c in name):
                continue

            is_single_word = len(words) == 1

            if etype == "person":
                # Check if this matches a known person (fuzzy matching)
                en_matched = (
                    name.lower() if name.lower() in existing_set
                    else _fuzzy_match_existing(name, existing_set)
                )
                if en_matched:
                    confidence = 0.75
                    # Use canonical form
                    for ep in existing_people:
                        if ep.lower() == en_matched:
                            name = ep
                            break
                else:
                    # EN model on Polish text is very noisy for unknown persons
                    confidence = 0.3
            else:
                confidence = 0.4

            entities.append(ExtractedEntity(text=name, type=etype, confidence=confidence))

    return entities


# ---------------------------------------------------------------------------
# Regex fallback (when spaCy is not installed)
# ---------------------------------------------------------------------------
_STANDALONE_NAME_RE = re.compile(
    r"\b((?:Dr|Mr|Mrs|Ms|Prof)\.?\s+)?"
    r"([A-ZÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻẞ][a-zà-öø-ÿąćęłńóśźżß]+"
    r"\s+[A-ZÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻẞ][a-zà-öø-ÿąćęłńóśźżß]+"
    r"(?:\s+[A-ZÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻẞ][a-zà-öø-ÿąćęłńóśźżß]+)?)\b"
)

_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\b", re.I),
    re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b", re.I),
    re.compile(r"\b((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b", re.I),
    re.compile(r"\b(yesterday|today|tomorrow|last week|next week|this week)\b", re.I),
    re.compile(r"\b((?:poniedziałe?k|wtore?k|środ[aęy]|czwarte?k|piąte?k|sobot[aęy]|niedziel[aęy])[a-ząćęłńóśźż]*)\b", re.I),
]

_PROJECT_RE = re.compile(
    r"(?:project|initiative|program|projekt)[:\s]+"
    r"([A-ZÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻẞ][\w\s-]{2,30}?)(?:[,.\n]|$)",
    re.I,
)

_SKIP_NAMES = frozenset({
    "The", "This", "That", "There", "These", "Those", "What", "When",
    "Where", "Which", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday", "January", "February", "March",
    "April", "May", "June", "July", "August", "September", "October",
    "November", "December", "New York", "United States", "San Francisco",
    "HTTP", "HTML", "JSON", "YAML", "TODO", "NOTE", "FIXME",
})


def _extract_with_regex(text: str, existing_people: List[str]) -> List[ExtractedEntity]:
    """Regex-based fallback for person extraction when spaCy is not available."""
    entities: List[ExtractedEntity] = []
    existing_set = {p.lower() for p in existing_people}

    for match in _STANDALONE_NAME_RE.finditer(text):
        name = match.group(2).strip()
        if name in _SKIP_NAMES or len(name) < 4:
            continue
        confidence = 0.7 if name.lower() in existing_set else 0.4
        entities.append(ExtractedEntity(text=name, type="person", confidence=confidence))

    return entities


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_entities(text: str, existing_people: List[str] = None) -> List[ExtractedEntity]:
    """Extract entities from note text.

    Uses spaCy NER (Polish + English) for persons/orgs when available,
    regex fallback otherwise. Dates and projects always use regex patterns.
    existing_people: known person labels from graph, used to boost confidence.
    """
    if not text:
        return []

    people = existing_people or []
    entities: List[ExtractedEntity] = []

    # Person/org extraction: spaCy if available, regex fallback
    if _load_spacy():
        entities.extend(_extract_with_spacy(text, people))
    else:
        entities.extend(_extract_with_regex(text, people))

    # Dates — always regex (reliable, language-agnostic)
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            entities.append(ExtractedEntity(
                text=match.group(1) if match.lastindex else match.group(0),
                type="date",
                confidence=0.9,
            ))

    # Projects — always regex
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
