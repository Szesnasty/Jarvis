"""Markdown chunking service for chunk-level embeddings.

Splits markdown notes into meaningful chunks by heading boundaries,
with sliding window fallback for long sections. Each chunk carries
context (title, section heading) so embeddings know provenance.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from utils.markdown import parse_frontmatter

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


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
) -> List[Chunk]:
    """Split markdown content into semantically meaningful chunks.

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
    heading_matches = list(_HEADING_RE.finditer(body))

    if not heading_matches:
        # No headings — treat entire body as one section
        sections.append(("", body))
    else:
        # Text before first heading (intro)
        intro = body[:heading_matches[0].start()].strip()
        if intro:
            sections.append(("", intro))

        for i, match in enumerate(heading_matches):
            heading_text = match.group(0).strip()  # e.g. "## Goals"
            start = match.end()
            end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(body)
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
        parts = []
        if title:
            parts.append(title)
        if section_title:
            parts.append(section_title)
        if tag_str and len(chunks) == 0:
            # Include tags only in first chunk
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
