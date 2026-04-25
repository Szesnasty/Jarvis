"""Markdown chunking service for chunk-level embeddings.

Multi-granularity strategy: each note produces several *kinds* of chunks
that intentionally overlap so retrieval has many high-signal targets.

For a single Jira issue we typically emit:
  1. **Anchor chunk** – frontmatter summary (key, title, status, priority,
     assignee, epic, sprint).  Strong target for "OPS-26"-style queries.
  2. **Section chunks** – one chunk per markdown section (Description,
     Acceptance criteria, Technical notes, Comments, …).  When a section
     is long, it is split with a sliding window of ~50 % overlap.
  3. **Bullet chunks** – sections that contain a list (acceptance
     criteria, reproduction steps, comments) also emit one chunk per
     bullet so each criterion is independently retrievable.
  4. **Coarse cross-section windows** – a single sliding window is rolled
     over the *entire* body so chunks span heading boundaries.  This
     gives multi-section context that pure section chunks miss.

Chunks share text on purpose – the resulting overlap massively increases
recall at retrieval time for relatively little extra storage.
"""

from dataclasses import dataclass
from typing import List, Optional

from utils.markdown import parse_frontmatter


# --------------------------------------------------------------------------- #
# Heading / structural parsing                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class _HeadingMatch:
    """Represents a markdown heading found by line-by-line scan."""
    start: int   # byte offset in body where the heading line starts
    end: int     # byte offset just past the heading line (before \n)
    line: str    # the full heading line, stripped


def _find_headings(body: str) -> List[_HeadingMatch]:
    """Find markdown headings without regex to avoid ReDoS risk."""
    matches: List[_HeadingMatch] = []
    pos = 0
    for raw_line in body.split("\n"):
        stripped = raw_line.strip()
        # A valid markdown heading: starts with 1-6 '#' followed by a space
        if stripped and stripped[0] == "#":
            hashes = 0
            for ch in stripped:
                if ch == "#":
                    hashes += 1
                else:
                    break
            if 1 <= hashes <= 6 and len(stripped) > hashes and stripped[hashes] == " ":
                matches.append(_HeadingMatch(
                    start=pos,
                    end=pos + len(raw_line),
                    line=stripped,
                ))
        pos += len(raw_line) + 1  # +1 for the \n
    return matches


def _extract_paragraphs(section_text: str) -> List[str]:
    """Return individual paragraph blocks (split by blank lines)."""
    blocks: List[str] = []
    current: List[str] = []
    for line in section_text.split("\n"):
        if line.strip() == "":
            if current:
                blocks.append(" ".join(s.strip() for s in current).strip())
                current = []
        else:
            # skip lines that are pure list markers (bullets handled separately)
            stripped = line.lstrip()
            if stripped.startswith(("* ", "- ", "+ ")):
                continue
            current.append(line)
    if current:
        blocks.append(" ".join(s.strip() for s in current).strip())
    return [b for b in blocks if b]


def _extract_bullets(section_text: str) -> List[str]:
    """Return individual bullet items found in *section_text*.

    Recognises ``* foo``, ``- foo`` and ``1. foo`` style lists.  Multi-line
    bullets (continuation indented or wrapped) are joined into one item.
    Returns an empty list if fewer than two bullets are present (so we
    don't waste an embedding on a single-line list).
    """
    items: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            text = " ".join(s.strip() for s in current).strip()
            if text:
                items.append(text)
            current.clear()

    for raw_line in section_text.split("\n"):
        line = raw_line.rstrip()
        stripped = line.lstrip()

        is_bullet = False
        payload = ""
        if stripped.startswith(("* ", "- ", "+ ")):
            is_bullet = True
            payload = stripped[2:].strip()
        elif len(stripped) > 2 and stripped[0].isdigit():
            # numbered list: "1. foo" / "12) foo"
            i = 0
            while i < len(stripped) and stripped[i].isdigit():
                i += 1
            if i + 1 < len(stripped) and stripped[i] in ".)" and stripped[i + 1] == " ":
                is_bullet = True
                payload = stripped[i + 2:].strip()

        if is_bullet:
            flush()
            current.append(payload)
        elif current and stripped and (raw_line.startswith(" ") or raw_line.startswith("\t")):
            # continuation of previous bullet
            current.append(stripped)
        else:
            flush()

    flush()
    return items if len(items) >= 2 else []


# --------------------------------------------------------------------------- #
# Token utilities                                                              #
# --------------------------------------------------------------------------- #


@dataclass
class Chunk:
    index: int
    section_title: str  # "" for intro / synthetic, "## Goals" for a section
    text: str
    token_count: int  # approximate: len(text.split())


def _approx_tokens(text: str) -> int:
    return len(text.split())


def _sliding_window(
    text: str,
    context_prefix: str,
    max_tokens: int,
    overlap_tokens: int,
    section_title: str,
) -> List[Chunk]:
    """Split *text* into overlapping windows.  Index is filled later."""
    words = text.split()
    chunks: List[Chunk] = []
    if not words:
        return chunks

    pos = 0
    step = max(1, max_tokens - overlap_tokens)

    while pos < len(words):
        end = min(pos + max_tokens, len(words))
        window = " ".join(words[pos:end])
        full = f"{context_prefix}{window}" if context_prefix else window
        chunks.append(Chunk(
            index=0,
            section_title=section_title,
            text=full,
            token_count=_approx_tokens(full),
        ))
        if end >= len(words):
            break
        pos += step

    return chunks


# --------------------------------------------------------------------------- #
# Anchor chunk (frontmatter summary)                                           #
# --------------------------------------------------------------------------- #


# Frontmatter keys, in display order, that should appear in the anchor chunk
# for *any* note.  Jira-specific fields are added on top when the subject is
# a jira_issue.
_ANCHOR_FIELDS_GENERIC = ("title", "tags", "type")
_ANCHOR_FIELDS_JIRA = (
    "issue_key",
    "title",
    "issue_type",
    "status",
    "priority",
    "assignee",
    "reporter",
    "epic",
    "parent",
    "sprint",
    "components",
    "labels",
)


def _anchor_text(fm: dict, subject_kind: str) -> str:
    """Synthesise a one-line summary of the note for the anchor chunk."""
    fields = _ANCHOR_FIELDS_JIRA if subject_kind == "jira_issue" else _ANCHOR_FIELDS_GENERIC
    parts: List[str] = []
    for key in fields:
        val = fm.get(key)
        if val in (None, "", [], {}):
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val if v)
            if not val:
                continue
        parts.append(f"{key}: {val}")
    return ". ".join(parts)


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


def chunk_markdown(
    content: str,
    title: str = "",
    tags: Optional[List[str]] = None,
    max_chunk_tokens: int = 110,          # smaller windows -> more chunks
    overlap_tokens: int = 55,             # ~50 % overlap
    min_window_tokens: int = 25,          # sections shorter than this stay one chunk
    coarse_window_tokens: int = 160,      # cross-section pass window size
    coarse_overlap_tokens: int = 80,      # cross-section overlap
    extra_coarse_window_tokens: int = 280,  # second coarse pass (long-range context)
    extra_coarse_overlap_tokens: int = 140,
    paragraph_min_tokens: int = 20,       # paragraphs >= this become own chunks
    subject_kind: str = "note",
    multi_granularity: bool = True,
    long_prose_threshold_tokens: int = 4000,  # auto-switch to lean mode above this
    long_prose_section_window: int = 220,    # bigger windows in long-prose mode
    long_prose_section_overlap: int = 60,    # ~25% overlap (vs 50% default)
) -> List[Chunk]:
    """Split markdown content into many overlapping, high-signal chunks.

    The result intentionally contains overlap between chunks – multiple
    granularities of the same content are emitted so retrieval has lots
    of relevant targets.

    Pipeline:
      1. Frontmatter parse + anchor synthesis
      2. Section split by markdown headings
      3. Section chunks (with ~50 % overlap when section >= ``min_window_tokens``)
      4. Per-bullet chunks for sections containing 2+ list items
      5. Coarse cross-section sliding window across the whole body
      6. Extra-coarse sliding window (longer windows) for long-range context
    """
    fm, body = parse_frontmatter(content)

    if not title:
        title = fm.get("title", "")
    if tags is None:
        raw_tags = fm.get("tags", [])
        tags = [str(t) for t in raw_tags] if raw_tags else []

    body = body.strip()
    chunks: List[Chunk] = []
    tag_str = ", ".join(tags) if tags else ""

    # ---- 1. Anchor chunk ---------------------------------------------------
    anchor = _anchor_text(fm, subject_kind) if multi_granularity else ""
    if anchor:
        chunks.append(Chunk(
            index=0,
            section_title="@anchor",
            text=anchor,
            token_count=_approx_tokens(anchor),
        ))

    if not body:
        if not chunks:
            text = f"{title}. {tag_str}." if tag_str else f"{title}."
            chunks.append(Chunk(index=0, section_title="", text=text.strip(),
                                token_count=_approx_tokens(text)))
        for i, c in enumerate(chunks):
            c.index = i
        return chunks

    # ---- 2. Section split --------------------------------------------------
    sections: List[tuple] = []  # (section_title, section_text)
    heading_matches = _find_headings(body)

    if not heading_matches:
        sections.append(("", body))
    else:
        intro = body[:heading_matches[0].start].strip()
        if intro:
            sections.append(("", intro))
        for i, match in enumerate(heading_matches):
            heading_text = match.line
            start = match.end
            end = heading_matches[i + 1].start if i + 1 < len(heading_matches) else len(body)
            section_body = body[start:end].strip()
            if section_body:
                sections.append((heading_text, section_body))

    # ---- 2a. Long-prose detection -----------------------------------------
    # PDF-extracted papers / books arrive as one mega-section with no
    # markdown structure and tens of thousands of words. Running the full
    # multi-granularity pipeline (section + bullet + paragraph + 2× coarse)
    # over an unstructured wall of text produces ~6× duplicated chunks
    # that all match the same query, killing retrieval diversity.
    #
    # Detect the case (no headings + body above the long-prose threshold)
    # and switch to a leaner config: bigger section window, lower overlap,
    # skip the bullet/paragraph passes and the extra-coarse pass.
    is_long_prose = (
        multi_granularity
        and not heading_matches
        and _approx_tokens(body) > long_prose_threshold_tokens
    )
    if is_long_prose:
        max_chunk_tokens = long_prose_section_window
        overlap_tokens = long_prose_section_overlap

    # ---- 3. Section chunks (with overlap) ---------------------------------
    for section_title, section_text in sections:
        # Build context prefix – title + section + (tags for jira)
        prefix_parts: List[str] = []
        if title:
            prefix_parts.append(title)
        if section_title:
            prefix_parts.append(section_title)
        if tag_str and (subject_kind == "jira_issue" or len(chunks) <= 1):
            prefix_parts.append(tag_str)
        context_prefix = ". ".join(prefix_parts) + ". " if prefix_parts else ""

        section_tokens = _approx_tokens(section_text)

        # Short section -> keep as one chunk
        if section_tokens < min_window_tokens:
            full_text = f"{context_prefix}{section_text}"
            chunks.append(Chunk(
                index=0,
                section_title=section_title,
                text=full_text,
                token_count=_approx_tokens(full_text),
            ))
        else:
            # Medium / long section -> overlapping windows.  This is the
            # *key* change vs. the old behaviour: even sections that fit
            # in ``max_chunk_tokens`` get sliced when they cross
            # ``min_window_tokens``, which produces overlap deliberately.
            chunks.extend(_sliding_window(
                section_text,
                context_prefix,
                max_chunk_tokens,
                overlap_tokens,
                section_title,
            ))

        # ---- 4. Per-bullet chunks ----------------------------------------
        if multi_granularity and not is_long_prose:
            bullets = _extract_bullets(section_text)
            for bullet in bullets:
                if _approx_tokens(bullet) < 2:
                    continue  # skip trivial bullets only
                bullet_text = f"{context_prefix}- {bullet}"
                chunks.append(Chunk(
                    index=0,
                    section_title=f"{section_title} > bullet" if section_title else "> bullet",
                    text=bullet_text,
                    token_count=_approx_tokens(bullet_text),
                ))

        # ---- 4b. Per-paragraph chunks (prose-heavy sections) -------------
        if multi_granularity and not is_long_prose:
            paragraphs = _extract_paragraphs(section_text)
            # Only emit per-paragraph chunks when there are multiple
            # substantive prose paragraphs (so we don't duplicate a
            # single-paragraph section that's already a chunk).
            if len(paragraphs) >= 2:
                for para in paragraphs:
                    if _approx_tokens(para) < paragraph_min_tokens:
                        continue
                    para_text = f"{context_prefix}{para}"
                    chunks.append(Chunk(
                        index=0,
                        section_title=f"{section_title} > paragraph" if section_title else "> paragraph",
                        text=para_text,
                        token_count=_approx_tokens(para_text),
                    ))

    # ---- 5. Coarse cross-section sliding window ---------------------------
    if multi_granularity and _approx_tokens(body) > coarse_window_tokens:
        coarse_prefix_parts: List[str] = []
        if title:
            coarse_prefix_parts.append(title)
        if tag_str:
            coarse_prefix_parts.append(tag_str)
        coarse_prefix = ". ".join(coarse_prefix_parts) + ". " if coarse_prefix_parts else ""

        chunks.extend(_sliding_window(
            body,
            coarse_prefix,
            coarse_window_tokens,
            coarse_overlap_tokens,
            "@coarse",
        ))

    # ---- 6. Extra-coarse pass (long-range context) -----------------------
    # A second sliding window with a larger window size captures
    # multi-paragraph relationships the fine coarse pass misses.
    # Skipped for long-prose docs — the (already widened) section pass
    # plus the coarse pass cover the same ground.
    if (
        multi_granularity
        and not is_long_prose
        and _approx_tokens(body) > extra_coarse_window_tokens
    ):
        coarse_prefix_parts2: List[str] = []
        if title:
            coarse_prefix_parts2.append(title)
        if tag_str:
            coarse_prefix_parts2.append(tag_str)
        coarse_prefix2 = ". ".join(coarse_prefix_parts2) + ". " if coarse_prefix_parts2 else ""

        chunks.extend(_sliding_window(
            body,
            coarse_prefix2,
            extra_coarse_window_tokens,
            extra_coarse_overlap_tokens,
            "@coarse-long",
        ))

    # Defensive fallback - body present but somehow no chunks emitted
    if not chunks:
        text = f"{title}. {tag_str}." if tag_str else f"{title}."
        chunks.append(Chunk(index=0, section_title="", text=text.strip(),
                            token_count=_approx_tokens(text)))

    # Renumber sequentially
    for i, chunk in enumerate(chunks):
        chunk.index = i

    return chunks
