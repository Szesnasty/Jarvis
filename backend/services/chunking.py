"""Markdown chunking service for chunk-level embeddings.

Splits markdown notes into meaningful chunks by heading boundaries,
with sliding window fallback for long sections. Each chunk carries
context (title, section heading) so embeddings know provenance.
"""

from dataclasses import dataclass
from typing import List, Optional

from utils.markdown import parse_frontmatter


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


@dataclass
class Chunk:
    index: int
    section_title: str  # "" for intro, "## Goals" for a section
    text: str
    token_count: int  # approximate: len(text.split())


def _approx_tokens(text: str) -> int:
    return len(text.split())


def _sliding_window(
    text: str,
    context_prefix: str,
    max_tokens: int,
    overlap_tokens: int,
    start_index: int,
    section_title: str,
) -> List[Chunk]:
    """Split a long text block into overlapping windows."""
    words = text.split()
    chunks: List[Chunk] = []
    pos = 0
    idx = start_index

    while pos < len(words):
        end = min(pos + max_tokens, len(words))
        window_text = " ".join(words[pos:end])
        full_text = f"{context_prefix}{window_text}" if context_prefix else window_text
        chunks.append(Chunk(
            index=idx,
            section_title=section_title,
            text=full_text,
            token_count=_approx_tokens(full_text),
        ))
        idx += 1
        if end >= len(words):
            break
        pos = end - overlap_tokens

    return chunks


def chunk_markdown(
    content: str,
    title: str = "",
    tags: Optional[List[str]] = None,
    max_chunk_tokens: int = 300,
    overlap_tokens: int = 50,
    subject_kind: str = "note",
) -> List[Chunk]:
    """Split markdown content into semantically meaningful chunks.

    Args:
        subject_kind: hint for section weighting. On ``jira_issue``, the
            title is repeated in every chunk prefix to boost relevance.

    Strategy:
    1. Parse frontmatter to extract title + tags
    2. Split body by markdown headings
    3. Each section <= max_chunk_tokens -> one chunk
    4. Longer sections -> sliding window with overlap
    5. Prepend title/section context to each chunk
    """
    fm, body = parse_frontmatter(content)

    if not title:
        title = fm.get("title", "")
    if tags is None:
        raw_tags = fm.get("tags", [])
        tags = [str(t) for t in raw_tags] if raw_tags else []

    body = body.strip()
    if not body:
        # Empty body — single chunk with just title + tags
        tag_str = ", ".join(tags) if tags else ""
        text = f"{title}. {tag_str}." if tag_str else f"{title}."
        return [Chunk(index=0, section_title="", text=text.strip(), token_count=_approx_tokens(text))]

    # Split body into sections by headings
    sections: List[tuple] = []  # (section_title, section_text)
    heading_matches = _find_headings(body)

    if not heading_matches:
        # No headings — treat entire body as one section
        sections.append(("", body))
    else:
        # Text before first heading (intro)
        intro = body[:heading_matches[0].start].strip()
        if intro:
            sections.append(("", intro))

        for i, match in enumerate(heading_matches):
            heading_text = match.line  # e.g. "## Goals"
            start = match.end
            end = heading_matches[i + 1].start if i + 1 < len(heading_matches) else len(body)
            section_body = body[start:end].strip()
            if section_body:
                sections.append((heading_text, section_body))

    if not sections:
        tag_str = ", ".join(tags) if tags else ""
        text = f"{title}. {tag_str}." if tag_str else f"{title}."
        return [Chunk(index=0, section_title="", text=text.strip(), token_count=_approx_tokens(text))]

    # Build chunks from sections
    chunks: List[Chunk] = []
    tag_str = ", ".join(tags) if tags else ""

    for section_title, section_text in sections:
        # Context prefix for embedding: title + section heading
        # For jira_issue subjects, always include title for relevance
        parts = []
        if title:
            parts.append(title)
        if section_title:
            parts.append(section_title)
        if tag_str and (len(chunks) == 0 or subject_kind == "jira_issue"):
            # Include tags in first chunk; for jira issues include in all
            parts.append(tag_str)

        context_prefix = ". ".join(parts) + ". " if parts else ""
        section_tokens = _approx_tokens(section_text)

        if section_tokens <= max_chunk_tokens:
            full_text = f"{context_prefix}{section_text}"
            chunks.append(Chunk(
                index=len(chunks),
                section_title=section_title,
                text=full_text,
                token_count=_approx_tokens(full_text),
            ))
        else:
            # Sliding window for long sections
            window_chunks = _sliding_window(
                section_text,
                context_prefix,
                max_chunk_tokens,
                overlap_tokens,
                start_index=len(chunks),
                section_title=section_title,
            )
            chunks.extend(window_chunks)

    # Fix indices (ensure sequential)
    for i, chunk in enumerate(chunks):
        chunk.index = i

    return chunks
