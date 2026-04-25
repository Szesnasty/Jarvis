import logging
import re
from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Tuple

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
    # Conversation formatting artifacts
    "User", "Jarvis", "Conversation", "Topics", "Related Notes",
    "Jarvis App",
})

# Patterns that look like person names but are actually markdown/tool artifacts
_JUNK_NAME_RE = re.compile(
    r'^(search_notes|read_note|write_note|append_note|create_plan|update_plan|'
    r'query_graph|web_search|save_preference|create_specialist|'
    r'have connections?|mind for|Related Notes|Conversation)$',
    re.I,
)

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
    # Polish pronouns/words that spaCy misclassifies
    "jego", "jej", "ich", "twoja", "twój", "moja", "mój",
    "twoje", "twoich", "twoi", "twoim", "swoich", "swoje", "swój",
    "moje", "moich", "moi", "moim",
    "nie", "tak", "jeśli", "jednak", "osobisty", "zapisałem",
    "porady", "porady adama", "however", "don'", "don't",
    # Polish words that start with uppercase at sentence start
    "jak", "ale", "gdzie", "kiedy", "dlaczego", "kto", "czy",
    "więc", "potem", "tutaj", "teraz", "właśnie", "naprawdę",
    "oczywiście", "pewnie", "chyba", "proszę", "dzięki", "hej",
    "cześć", "witaj", "witam", "dobry", "dzień", "wieczór",
    "jestem", "masz", "wiem", "mogę", "chcę", "musisz",
    "możesz", "powiedz", "powiem", "zobaczmy", "zobaczę",
    "pani", "pana", "adama", "tomka",
    "pamiętam", "imię", "imie", "mam", "na", "imi",
    "dzisiaj", "jutro", "wczoraj", "rano", "wieczorem",
    "dobrze", "jasne", "okej", "super", "fajnie", "świetnie",
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

# Words that are never the first token of a real person/org name. spaCy
# routinely captures sentence fragments that start with one of these
# (e.g. "With Deep Learning", "For Crows - Pairs", "By Sampling From").
# Rejecting on the first token alone catches most bibliography artifacts.
_PREPOSITION_LEAD = frozenset({
    # English prepositions / articles / conjunctions
    "with", "from", "by", "for", "about", "after", "before", "during",
    "under", "over", "through", "of", "in", "on", "at", "to", "into",
    "onto", "upon", "toward", "towards", "across", "against", "among",
    "around", "behind", "below", "beneath", "beside", "between",
    "beyond", "despite", "except", "following", "including", "inside",
    "like", "near", "outside", "past", "since", "until", "within",
    "without", "such", "these", "those", "this", "that", "an", "the",
    "and", "or", "but", "if", "while", "because", "although", "though",
    "however", "moreover", "therefore", "furthermore", "additionally",
    "specifically", "namely", "particularly", "especially",
    "as", "when", "where", "whereas", "whether",
    # English auxiliaries / verbs that look capitalised in section starts
    "is", "are", "was", "were", "be", "being", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "can",
    # Time words that get capitalised after periods
    "today", "tomorrow", "yesterday", "now", "later", "soon",
})

# Common English nouns that spaCy frequently misclassifies as ORG when
# they appear capitalised at the start of a section, table caption, or
# heading (e.g. "Accuracy", "Training Data"). These are NEVER organisations
# in a personal knowledge graph.
_GENERIC_ENGLISH_NOUNS = frozenset({
    # Section / paper structure
    "abstract", "introduction", "background", "discussion", "conclusion",
    "conclusions", "method", "methods", "methodology", "approach",
    "approaches", "result", "results", "experiment", "experiments",
    "evaluation", "evaluations", "analysis", "limitations",
    "acknowledgements", "acknowledgments", "references", "appendix",
    "figure", "figures", "table", "tables", "section", "sections",
    "chapter", "chapters", "page", "pages", "paragraph", "summary",
    # Generic concepts often capitalised
    "accuracy", "performance", "quality", "training", "training data",
    "test data", "validation", "evaluation", "implementation",
    "architecture", "architectures", "model", "models", "system",
    "systems", "feedback", "input", "output", "data", "dataset",
    "datasets", "benchmark", "benchmarks", "task", "tasks",
    "framework", "frameworks", "pipeline", "pipelines", "process",
    "processes", "function", "functions", "feature", "features",
    "parameter", "parameters", "objective", "loss", "metric",
    "metrics", "score", "scores", "rate", "rates", "step", "steps",
    # Tech umbrella terms
    "artificial intelligence", "machine learning", "deep learning",
    "natural language", "computer vision",
    # Reference fragments
    "see figure", "see table", "see section", "et al",
    # Polish equivalents for completeness
    "wstęp", "podsumowanie", "wnioski", "metoda", "metody", "wyniki",
    "rysunek", "tabela", "rozdział", "strona",
})

# Maximum word count for a real person/org name. Anything longer is almost
# certainly a sentence fragment.
_MAX_NAME_TOKENS = 5

# Characters that disqualify an entity (bibliography fragments, sentence
# splits, etc.). Apostrophes and dots (for initials) are allowed.
_INVALID_NAME_PATTERN = re.compile(r"[\d/\\\(\)\[\]\{\}<>=+*&^%$#@~`|;:?!]")

# Tech / domain acronyms that spaCy routinely tags as ORG when they
# appear capitalised in academic prose. They're concepts, not entities,
# and they create huge fan-in stars (one paper mentions "LLM" 200 times).
# Real organisations that happen to be acronyms (IBM, NASA, OECD, IEEE,
# NIST, ACM) are rare enough that we accept the small recall loss in
# exchange for a much cleaner graph. Add to the allow-list below if needed.
_ACRONYM_DENY: FrozenSet[str] = frozenset({
    # AI/ML model & technique acronyms
    "ai", "ml", "dl", "rl", "nlp", "cv", "nlg", "nlu", "ir",
    "llm", "llms", "lm", "lms", "slm", "slms", "plm", "plms",
    "gpt", "bert", "t5", "elmo", "mlm", "clm", "rlm", "rlhf",
    "rnn", "cnn", "lstm", "gru", "mlp", "ffn", "moe", "vae", "gan",
    "cot", "tot", "sft", "ppo", "dpo", "kto", "rag", "icl", "few-shot",
    "palm", "lamda", "llama", "mistral", "claude", "gemini",
    # Hardware
    "gpu", "gpus", "tpu", "tpus", "cpu", "cpus", "ram", "rom", "ssd",
    # Software / interface
    "api", "apis", "url", "urls", "sdk", "cli", "gui", "tui", "rest",
    "json", "xml", "yaml", "html", "css", "sql", "ssh", "tcp", "udp",
    "http", "https", "ip", "dns", "vpn",
    # Generic process
    "ci", "cd", "qa", "qe", "ux", "ui", "pr", "prs", "ci/cd",
    # Compound that often slips through
    "cot", "ai/ml",
})

# Single allow-list of legitimate acronymic organisations. Keep small;
# extend on demand. Lowercase keys for case-insensitive comparison.
_ACRONYM_ORG_ALLOW: FrozenSet[str] = frozenset({
    "ibm", "nasa", "oecd", "ieee", "nist", "acm", "mit", "ucl",
    "fbi", "cia", "nsa", "epa", "fda", "cdc", "who", "un", "eu",
    "google", "apple", "amazon", "microsoft", "meta", "openai",
    "anthropic", "deepmind",
})

# Substrings that signal a PDF text-extraction artifact: prepositions /
# articles that ended up *inside* a single token because the PDF→text pass
# lost the whitespace between words. Real names never contain these.
_PDF_FUSED_SUBSTRINGS: Tuple[str, ...] = (
    "ofthe", "andthe", "forthe", "tothe", "fromthe", "inthe", "withthe",
    "ofcommerce", "ofdefense", "ofstate", "ofjustice", "ofhealth",
    "department", "appendix", "categoriesand", "subcategoriesfor",
    "identifyingcontextual", "adaptedfrom",
)

# Generic AI/ML domain words that spaCy frequently slings together as
# title-case "person" or "org" candidates ("Adapter Tuning", "Domain
# Expert", "Internal Feedback", "Generative Agents"). When a multi-word
# candidate consists *entirely* of these words it is rejected.
_DOMAIN_GENERIC_TOKENS: FrozenSet[str] = frozenset({
    "adapter", "adapters", "tuning", "fine-tuning", "finetuning",
    "encoder", "encoders", "decoder", "decoders", "transformer",
    "transformers", "embedding", "embeddings", "attention",
    "model", "models", "modeling", "modelling", "agent", "agents",
    "alignment", "feedback", "expert", "experts", "techniques",
    "exploration", "explorations", "variant", "variants",
    "domain", "internal", "external", "human", "machine",
    "natural", "neural", "deep", "shallow", "supervised",
    "unsupervised", "reinforcement", "self", "auto",
    "input", "output", "data", "training", "evaluation", "evaluation",
    "test", "validation", "context", "contextual", "prefix", "suffix",
    "key", "value", "query", "head", "layer", "block", "loss",
    "score", "ranking", "retrieval", "generation", "generative",
    "generation", "summarization", "translation", "classification",
    "regression", "clustering", "policy", "reward", "instruction",
    "instructions", "prompt", "prompts", "prompting", "chain",
    "thought", "reasoning", "planning", "search", "memory",
    "collection", "dataset", "datasets", "benchmark", "benchmarks",
    "framework", "method", "methods", "approach", "approaches",
    "system", "systems", "pipeline", "feature", "features",
    "objective", "metric", "metrics", "task", "tasks",
    "early", "late", "recent", "next", "previous", "current",
    "first", "second", "third", "final", "initial",
    "third-party", "third",
    # Common AI architecture / engineering nouns
    "architecture", "architectures",
    "labeler", "labelers", "selection", "selections",
    "arena", "chatbot", "chatbots",
    "request", "requests", "information",
    "review", "reviews", "process", "processes",
    "analysis", "analyses", "study", "studies",
})


def _is_pdf_fused_token(token: str) -> bool:
    """True for single tokens that are clearly fused PDF text fragments.

    Matches: very long tokens that contain glue substrings like ``ofthe``,
    ``forthe`` or ``department``, OR camelCase-joined runs of >= 14 chars
    where lowercase letters are followed by uppercase mid-token (a strong
    sign that whitespace was lost between words).
    """
    if len(token) < 14:
        return False
    lower = token.lower()
    for needle in _PDF_FUSED_SUBSTRINGS:
        if needle in lower:
            return True
    # Detect lowercase→uppercase boundaries inside the token (>=2 such
    # transitions => almost certainly a fused phrase like
    # "CategoriesandsubcategoriesfortheMANAGE").
    transitions = sum(
        1 for i in range(1, len(token))
        if token[i - 1].islower() and token[i].isupper()
    )
    return transitions >= 2


def _passes_structural_filters(name: str, etype: Optional[str] = None) -> bool:
    """Common structural rejects shared by both Polish and English NER paths.

    ``etype`` (optional) enables type-aware filtering: e.g. tech acronyms
    are rejected as organisations but a real person named "Wu" still
    passes when classified as person.
    """
    if not name:
        return False
    # Reject names with control characters (PDF metadata leak: null bytes,
    # form feeds, etc. show up as raw \x00 sequences when a font-encoded
    # string slipped into the extracted text).
    if any(ord(c) < 0x20 for c in name):
        return False
    tokens = name.split()
    if not tokens or len(tokens) > _MAX_NAME_TOKENS:
        return False
    first_lower = tokens[0].lower()
    if first_lower in _PREPOSITION_LEAD:
        return False
    # Reject candidates whose first token is a gerund / present participle
    # ("Improving MLLMs", "Building Models", "Using LLMs"). These are
    # sentence-start fragments, never names. Heuristic: token ends in
    # "ing", length >= 6, and starts with uppercase. We check that the
    # stem (without "ing") looks verby by requiring the original token to
    # be > 5 chars to avoid collateral on "King", "Bing", "Ming".
    first_token = tokens[0]
    if (
        len(first_token) >= 6
        and first_token.lower().endswith("ing")
        and first_token[0].isupper()
    ):
        return False
    last_lower = tokens[-1].lower().rstrip(".,;:")
    if last_lower in _PREPOSITION_LEAD:
        return False  # "by" / "and" trailing → bibliography fragment
    if name.lower() in _GENERIC_ENGLISH_NOUNS:
        return False
    if _INVALID_NAME_PATTERN.search(name):
        return False
    # Reject names where any single token is just one letter (initials are
    # OK with a trailing dot, but raw "K" alone marks bibliography fragments
    # like "Huang and K").
    for tok in tokens:
        bare = tok.rstrip(".,;:")
        if len(bare) == 1 and bare.isalpha():
            return False
    # PDF text-extraction fusion: any single token matching the fused
    # pattern means whitespace was lost — the candidate is not a real name.
    for tok in tokens:
        if _is_pdf_fused_token(tok):
            return False
    # Type-aware filters
    if etype == "organization":
        # Single short tech acronym → reject (LLM, GPT, NLP, …) unless on
        # the explicit allow-list.
        if len(tokens) == 1:
            single_lower = tokens[0].lower().rstrip("s.,;:")
            if single_lower in _ACRONYM_DENY and single_lower not in _ACRONYM_ORG_ALLOW:
                return False
            # Pure all-caps single token <= 4 chars that's *not* on the
            # allow-list is almost certainly a domain acronym, not an org.
            stripped = tokens[0].rstrip("s.,;:")
            if (
                len(stripped) <= 4
                and stripped.isupper()
                and single_lower not in _ACRONYM_ORG_ALLOW
            ):
                return False
    if etype == "person":
        # Multi-word candidate where every token is a generic domain word
        # → it's a noun phrase ("Adapter Tuning", "Domain Expert"), not a
        # person. Single-token persons are handled by confidence scoring
        # elsewhere; we don't reject "Ren" outright because it could be a
        # real surname.
        if len(tokens) >= 2:
            domain_lower = {t.lower().rstrip(".,;:") for t in tokens}
            if domain_lower.issubset(_DOMAIN_GENERIC_TOKENS):
                return False
        # Single-token short "person" names (<=3 chars) that are also in
        # the acronym deny set ("LM", "PR", "AI") → reject. Real surnames
        # of that length (Wu, Li, Xu) survive because they're not in
        # _ACRONYM_DENY.
        if len(tokens) == 1:
            single_lower = tokens[0].lower().rstrip("s.,;:")
            if single_lower in _ACRONYM_DENY:
                return False
    return True


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

    # Hard cap: spaCy is O(n) and very large texts (270 KB PDF sections) can
    # take minutes. Truncate to 20 000 chars — sufficient for name discovery.
    if len(text) > 20_000:
        text = text[:20_000]

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
        # Reject names containing apostrophes at edges (don', I'll, etc.)
        if name.endswith("'") or name.startswith("'"):
            continue
        # Reject names that are all lowercase (common words, not proper names)
        # Exception: if it matches a known person by fuzzy match, keep it
        if name[0].islower():
            if not (
                name.lower() in existing_set
                or _fuzzy_match_existing(name, existing_set)
            ):
                continue
        # Reject markdown/tool artifacts
        if _JUNK_NAME_RE.match(name):
            continue
        # Reject names starting with # (markdown headings)
        if name.startswith('#'):
            continue
        # Reject names wrapped in quotes
        if name.startswith('"') or name.startswith("'"):
            continue
        # Reject multi-word entities where ALL words are stop/non-person words
        words = name.split()
        if len(words) > 1 and all(
            w.lower() in _POLISH_NON_PERSON or w.lower() in _NOT_NAME_WORDS
            for w in words
        ):
            continue
        # Structural filters: prepositions/articles as first/last token,
        # generic English nouns, sentence fragments, single-letter tokens,
        # PDF text-extraction fusion, type-specific acronym filters.
        if not _passes_structural_filters(name, etype):
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
            # Reject multi-word entities where ALL words are stop/non-person words
            if len(name.split()) > 1 and all(
                w.lower() in _POLISH_NON_PERSON or w.lower() in _NOT_NAME_WORDS
                for w in name.split()
            ):
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
            # Same structural rejects as the PL path
            if not _passes_structural_filters(name, etype):
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
# Conversation text cleaning
# ---------------------------------------------------------------------------

_CONVERSATION_MARKERS_RE = re.compile(
    r'^\*\*(User|Jarvis)\*\*:\s*', re.MULTILINE,
)
_MARKDOWN_HEADING_RE = re.compile(r'^#{1,6}\s+.*$', re.MULTILINE)
_WIKI_LINK_RE = re.compile(r'\[\[([^|\]]+)(?:\|([^\]]+))?\]\]')


def clean_conversation_text(body: str) -> str:
    """Strip conversation formatting so entity extraction sees clean prose.

    Removes:
    - **User**: / **Jarvis**: prefixes
    - Markdown headings (## Conversation, ## Topics, etc.)
    - Wiki-link syntax [[path|label]] → label
    """
    text = _CONVERSATION_MARKERS_RE.sub('', body)
    text = _MARKDOWN_HEADING_RE.sub('', text)
    text = _WIKI_LINK_RE.sub(lambda m: m.group(2) or m.group(1), text)
    return text.strip()


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
