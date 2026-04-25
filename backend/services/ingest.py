import asyncio
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".csv", ".xml", ".json"}

# ── Document section split (steps 27a / 27d) ─────────────────────────────────
# When a document is long enough AND has enough natural break points, split
# it into one Markdown note per section plus an index note. Below either
# threshold the existing single-file path is used unchanged.
#
# Step 27a covered PDF only. Step 27d extends the same machinery to plain
# text, Markdown, JSON and large XML so the graph density gain isn't limited
# to a single format.
SECTION_SPLIT_MIN_CHARS = 30_000
SECTION_SPLIT_MIN_HEADINGS = 4
# Hard ceiling: very long papers can produce hundreds of false-positive
# headings; cap to avoid runaway file creation.
SECTION_SPLIT_MAX_SECTIONS = 60
# JSON list chunking: when the top-level is a list, group N items per
# section to avoid one note per item on huge arrays.
JSON_LIST_CHUNK_SIZE = 50
# Cap on inline rendered length per JSON section body (longer values get
# truncated with a marker so a single huge value can't blow up a note).
JSON_BODY_TRUNCATE = 60_000


class IngestError(Exception):
    pass


def _memory_dir(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _slugify(text: str) -> str:
    """NFKD-normalise then strip non-ASCII so Polish titles survive.

    'Mój dzień' → 'moj-dzien' instead of collapsing to ''.
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    # NFKD does not decompose ł/Ł, ø, đ, ß — map them explicitly so Polish
    # and other European stems collapse to ASCII rather than being stripped.
    extras = str.maketrans({
        "ł": "l", "Ł": "l",
        "đ": "d", "Đ": "d",
        "ø": "o", "Ø": "o",
        "ß": "ss",
    })
    ascii_only = ascii_only.translate(extras)
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def _unique_path(target: Path) -> Path:
    """If target exists, add numeric suffix."""
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    for i in range(1, 1001):
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise IngestError(f"Too many files with the same name: {target.name}")


def _unique_dir(target: Path) -> Path:
    """Like ``_unique_path`` but for directories. Returns a non-existing dir."""
    if not target.exists():
        return target
    parent = target.parent
    name = target.name
    for i in range(1, 1001):
        candidate = parent / f"{name}-{i}"
        if not candidate.exists():
            return candidate
    raise IngestError(f"Too many directories with the same name: {target.name}")


# ── Heading detection for PDF section split (step 27a) ─────────────────────

# Numbered: "1 Introduction", "2.3 Threat Model", "10. Conclusion"
_HEADING_NUMBERED_RE = re.compile(r"^\d+(?:\.\d+){0,2}\.?\s+\S+")
# Strict numbered heading used when blank-surround is missing (typical
# for pdfplumber output, which produces continuous text per page).
# Requires: 1- or 2-digit number, optional .X subsection, then a Title-cased
# title of 1–10 short words with no terminal period. This is precise enough
# to skip inline numerical references like "Table 3 shows ..." or "5.2 ms".
_HEADING_NUMBERED_STRICT_RE = re.compile(
    r"^\d{1,2}(?:\.\d{1,2})?\.?\s+[A-Z][\w\-'’/&: ,]{1,80}$"
)
# Table-of-contents entry: numbered heading whose title text ends with a
# trailing page number (e.g. "1.1 Publications 29"). These look like
# real headings but reference page numbers in the printed PDF, so they
# come from the TOC rather than the section itself.
_HEADING_TOC_TRAIL_RE = re.compile(r"\s+\d{1,4}$")
# All-caps: "ABSTRACT", "RELATED WORK" (≥ 4 chars, allows digits/punct)
_HEADING_ALLCAPS_RE = re.compile(r"^[A-Z][A-Z0-9 \-:&]{3,80}$")
# Title-case single line, up to 12 words, no trailing period
_HEADING_TITLECASE_RE = re.compile(r"^[A-Z][\w\- ,&:]{3,80}$")


def _is_top_level_numbered(line: str) -> bool:
    """A numbered heading is top-level if it has zero or one dots in numbering."""
    parts = line.split(None, 1)
    if not parts:
        return False
    head = parts[0].rstrip(".")
    return head.count(".") <= 1


def _is_heading_line(line: str) -> bool:
    """Heuristic: would this stripped line plausibly start a section?"""
    stripped = line.strip()
    n = len(stripped)
    if n < 4 or n > 120:
        return False
    if stripped.endswith("."):
        # Heading lines almost never end with a period (unlike sentences).
        # Exception: numbered headings like "1." are allowed but their
        # text part is checked separately below.
        if not _HEADING_NUMBERED_RE.match(stripped):
            return False
    if _HEADING_NUMBERED_RE.match(stripped):
        return True
    if _HEADING_ALLCAPS_RE.match(stripped):
        # Reject lines that look like sentences in caps (very long or
        # full of common-word patterns is hard to detect cheaply; the
        # length cap above handles the worst cases).
        return True
    # Title case: must have ≤ 12 words to look like a heading
    if _HEADING_TITLECASE_RE.match(stripped):
        words = stripped.split()
        if len(words) <= 12:
            # Reject if the line is almost certainly running prose:
            # e.g. starts with a function word.
            first = words[0].lower()
            if first in {"the", "a", "an", "this", "that", "these", "those",
                          "in", "on", "at", "for", "of", "to", "by", "with",
                          "and", "but", "or", "if", "when", "while"}:
                return False
            return True
    return False


@dataclass
class _DocumentSection:
    """Single section extracted from a long document.

    ``body`` is the ready-to-write Markdown body (no frontmatter). For
    plain-text/PDF extracts this is prose; for JSON/XML it's a fenced
    code block so the original structure stays readable.
    """
    title: str
    body: str


# Backwards-compatible alias used by the older PDF-only code paths and tests.
_PdfSection = _DocumentSection


def _detect_pdf_sections(text: str) -> List["_DocumentSection"]:
    """Detect top-level sections in PDF-extracted plain text.

    Returns a list of (title, body) sections in document order. Always
    includes a leading "Front Matter" section for content before the
    first detected heading, when that content is non-empty.

    Sections have whitespace-collapsed bodies but preserve paragraph
    breaks (double newlines).
    """
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    n = len(lines)

    # Identify candidate heading line indices.
    #
    # Two acceptance paths:
    #   (a) The line matches the *strict* numbered-heading regex
    #       (1- or 2-digit prefix + Title-cased short title). These are
    #       precise enough on their own that we do not require blank
    #       surround — pdfplumber output rarely has blank lines between
    #       paragraphs, so demanding both would reject every real
    #       heading in academic PDFs.
    #   (b) Any other heading-like line (ALL-CAPS, title-case, looser
    #       numbered) is only accepted when surrounded by blank lines
    #       (or file boundaries). This keeps inline phrases out.
    heading_indices: List[int] = []
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not _is_heading_line(raw):
            continue
        # Skip TOC entries: they look like real headings but their title
        # text ends with a printed page number ("1.1 Publications 29").
        if _HEADING_TOC_TRAIL_RE.search(stripped):
            continue
        if _HEADING_NUMBERED_STRICT_RE.match(stripped):
            heading_indices.append(i)
            continue
        prev_blank = i == 0 or lines[i - 1].strip() == ""
        next_blank = i + 1 >= n or lines[i + 1].strip() == ""
        if prev_blank and next_blank:
            heading_indices.append(i)

    # Filter to top-level only:
    #   - numbered: must be top-level by our rule
    #   - all-caps and title-case: kept as-is (they're already coarse)
    top_level: List[int] = []
    for idx in heading_indices:
        line = lines[idx].strip()
        if _HEADING_NUMBERED_RE.match(line):
            if _is_top_level_numbered(line):
                top_level.append(idx)
        else:
            top_level.append(idx)

    # If we matched many strict numbered headings, drop coarser candidates
    # entirely — they'd usually be accidental matches inside body text
    # (e.g. an ALL-CAPS acronym left on its own line).
    strict_count = sum(
        1
        for idx in top_level
        if _HEADING_NUMBERED_STRICT_RE.match(lines[idx].strip())
    )
    if strict_count >= SECTION_SPLIT_MIN_HEADINGS:
        top_level = [
            idx
            for idx in top_level
            if _HEADING_NUMBERED_STRICT_RE.match(lines[idx].strip())
        ]

    # Deduplicate: when the same heading text appears more than once
    # (TOC echo of the real section, repeated running header on every
    # page, etc.) keep only the LAST occurrence — that's the one with
    # the real body following it. Using ``last`` rather than ``first``
    # also prevents a TOC line from stealing all text up to the real
    # section as its "body".
    seen: Dict[str, int] = {}
    for idx in top_level:
        key = re.sub(r"\s+", " ", lines[idx].strip()).lower()
        seen[key] = idx
    top_level = sorted(seen.values())

    if not top_level:
        return []

    sections: List[_DocumentSection] = []

    # Front matter: everything before the first heading
    pre_text = "\n".join(lines[: top_level[0]]).strip()
    if pre_text:
        sections.append(_DocumentSection(title="Front Matter", body=pre_text))

    # Walk top-level headings, body = text up to next top-level heading
    for j, start in enumerate(top_level):
        title = lines[start].strip()
        end = top_level[j + 1] if j + 1 < len(top_level) else n
        body_lines = lines[start + 1 : end]
        body = "\n".join(body_lines).strip()
        sections.append(_DocumentSection(title=title, body=body))

    # Hard cap to prevent runaway false-positive heading explosions.
    if len(sections) > SECTION_SPLIT_MAX_SECTIONS:
        sections = sections[:SECTION_SPLIT_MAX_SECTIONS]
    return sections


# ── Markdown section detector ────────────────────────────────────────────────

# Top-level (#) and second-level (##) ATX headings. We avoid splitting on
# deeper levels because those are usually subsections inside a larger topic.
_MD_HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*#*\s*$")


def _detect_markdown_sections(text: str) -> List["_DocumentSection"]:
    """Split a Markdown document on its top-level (#, ##) headings.

    Front matter (text before the first heading) is preserved as a leading
    "Front Matter" section if non-empty. Sections retain their original
    Markdown body so headings, lists, code blocks and tables stay intact.
    """
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    in_fence = False
    heading_indices: List[int] = []
    for i, raw in enumerate(lines):
        stripped = raw.lstrip()
        # Track fenced code blocks so headings inside ``` aren't picked up.
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _MD_HEADING_RE.match(raw)
        if m:
            heading_indices.append(i)

    if not heading_indices:
        return []

    sections: List[_DocumentSection] = []
    pre_text = "\n".join(lines[: heading_indices[0]]).strip()
    if pre_text:
        sections.append(_DocumentSection(title="Front Matter", body=pre_text))

    for j, start in enumerate(heading_indices):
        m = _MD_HEADING_RE.match(lines[start])
        title = (m.group(2) if m else lines[start]).strip() or f"Section {j + 1}"
        end = heading_indices[j + 1] if j + 1 < len(heading_indices) else len(lines)
        body = "\n".join(lines[start + 1 : end]).strip()
        sections.append(_DocumentSection(title=title, body=body))

    if len(sections) > SECTION_SPLIT_MAX_SECTIONS:
        sections = sections[:SECTION_SPLIT_MAX_SECTIONS]
    return sections


# ── JSON section detector ────────────────────────────────────────────────────


def _json_dump(value) -> str:
    """Pretty-print a JSON-compatible value, with hard-cap truncation."""
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    if len(text) > JSON_BODY_TRUNCATE:
        text = text[:JSON_BODY_TRUNCATE] + "\n… (truncated)"
    return text


def _json_section_title(key: str, value) -> str:
    """Compose a readable section title for a top-level JSON key."""
    kind = type(value).__name__
    return f"{key} ({kind})"


def _detect_json_sections(parsed) -> List["_DocumentSection"]:
    """Produce one section per top-level key (dict) or per chunk (list).

    Returns an empty list when the structure is too small or scalar — the
    caller falls back to the single-note path. Bodies are wrapped in a
    fenced ```json``` block so the viewer keeps syntax highlighting and
    the original shape is preserved.
    """
    sections: List[_DocumentSection] = []

    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        if len(keys) < SECTION_SPLIT_MIN_HEADINGS:
            return []
        for key in keys:
            value = parsed[key]
            body = "```json\n" + _json_dump(value) + "\n```"
            sections.append(_DocumentSection(
                title=_json_section_title(str(key), value),
                body=body,
            ))
    elif isinstance(parsed, list):
        if len(parsed) < SECTION_SPLIT_MIN_HEADINGS:
            return []
        chunk = JSON_LIST_CHUNK_SIZE
        for start in range(0, len(parsed), chunk):
            end = min(start + chunk, len(parsed))
            body = "```json\n" + _json_dump(parsed[start:end]) + "\n```"
            sections.append(_DocumentSection(
                title=f"Items {start + 1}–{end}",
                body=body,
            ))
        # If the list was too short to produce ≥ MIN_HEADINGS chunks fall
        # back to single-note path (caller checks the length).
    else:
        return []

    if len(sections) > SECTION_SPLIT_MAX_SECTIONS:
        sections = sections[:SECTION_SPLIT_MAX_SECTIONS]
    return sections


def _make_frontmatter(title: str, source: str, tags: Optional[list] = None) -> str:
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm = {"title": title, "date": now, "source": source, "tags": tags or ["imported"]}
    # add_frontmatter prepends to body; we just want the frontmatter
    return add_frontmatter("", fm)


def _make_section_frontmatter(
    *,
    title: str,
    source: str,
    parent_path: str,
    section_index: int,
    doc_type: str = "pdf",
    tags: Optional[list] = None,
) -> str:
    """Frontmatter for a per-section note created by document section split."""
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm = {
        "title": title,
        "date": now,
        "source": source,
        "parent": parent_path,
        "section_index": section_index,
        "tags": tags or ["imported", doc_type, "section"],
    }
    return add_frontmatter("", fm)


def _make_index_frontmatter(title: str, source: str, doc_type: str = "pdf") -> str:
    """Frontmatter for the index note that links all sections."""
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fm = {
        "title": title,
        "date": now,
        "source": source,
        "tags": ["imported", doc_type, "document"],
        "document_type": f"{doc_type}-document",
    }
    return add_frontmatter("", fm)


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from PDF using pdfplumber if available, else fallback."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        raise IngestError("pdfplumber not installed. Install with: pip install pdfplumber")


async def _emit_document_sections(
    *,
    doc_type: str,
    title: str,
    source_path: Path,
    target_folder: str,
    workspace_path: Optional[Path],
    sections: List[_DocumentSection],
    job_id: Optional[str],
) -> Dict:
    """Write index + per-section notes for a long document and wire them up.

    Steps 27a / 27d. The index note links each section via ``[[wiki-link]]``
    so the bidirectional resolver in ``graph_service/builder.py`` produces
    forward and reverse edges. Smart Connect runs ONCE on the index;
    sections are reachable through the index hub, which keeps ingest
    cost roughly the same as a single file.

    ``doc_type`` ("pdf", "json", "xml", "markdown", "text") drives only
    the tags / document_type metadata — the file emission logic is the
    same for every supported format.
    """
    from services import ingest_jobs
    from services.memory_service import index_note_file

    def _stage(name: str) -> None:
        if job_id:
            ingest_jobs.update_stage(job_id, name)

    mem = _memory_dir(workspace_path)
    folder = mem / target_folder
    folder.mkdir(parents=True, exist_ok=True)

    doc_slug = _slugify(title) or "document"
    doc_dir = _unique_dir(folder / doc_slug)
    doc_dir.mkdir(parents=True, exist_ok=False)

    section_files: List[Path] = []
    section_titles: List[str] = []
    rel_doc_dir = doc_dir.relative_to(mem).as_posix()
    index_rel_path = f"{rel_doc_dir}/index.md"

    width = max(2, len(str(len(sections))))
    for i, section in enumerate(sections, start=1):
        slug = _slugify(section.title) or f"section-{i}"
        slug = slug[:60].rstrip("-") or f"section-{i}"
        fname = f"{str(i).zfill(width)}-{slug}.md"
        target = doc_dir / fname
        section_fm = _make_section_frontmatter(
            title=section.title,
            source=str(source_path),
            parent_path=index_rel_path,
            section_index=i,
            doc_type=doc_type,
        )
        await asyncio.to_thread(
            target.write_text, section_fm + section.body + "\n", encoding="utf-8"
        )
        section_files.append(target)
        section_titles.append(section.title)

    # Index note links each section as a wiki-link. Wiki targets are paths
    # relative to memory/ without the .md suffix, matching extract_wiki_links.
    index_lines = [f"# {title}", ""]
    for i, sf in enumerate(section_files, start=1):
        rel = sf.relative_to(mem).with_suffix("").as_posix()
        index_lines.append(f"{i}. [[{rel}]] — {section_titles[i - 1]}")
    index_body = "\n".join(index_lines) + "\n"
    index_fm = _make_index_frontmatter(title, str(source_path), doc_type=doc_type)
    index_path = doc_dir / "index.md"
    await asyncio.to_thread(
        index_path.write_text, index_fm + index_body, encoding="utf-8"
    )

    logger.info(
        "%s section split: %s -> %d sections under %s",
        doc_type.upper(), source_path.name, len(sections), rel_doc_dir,
    )

    total_size = 0
    try:
        total_size = await asyncio.to_thread(
            lambda: index_path.stat().st_size
            + sum(sf.stat().st_size for sf in section_files)
        )
    except FileNotFoundError:
        pass

    _stage("indexing")
    try:
        await index_note_file(index_rel_path, workspace_path=workspace_path)
        for sf in section_files:
            sf_rel = sf.relative_to(mem).as_posix()
            await index_note_file(sf_rel, workspace_path=workspace_path)
    except Exception as exc:
        # Best-effort cleanup of the whole document directory.
        try:
            for sf in section_files:
                sf.unlink(missing_ok=True)
            index_path.unlink(missing_ok=True)
            doc_dir.rmdir()
        except Exception:
            pass
        raise IngestError(f"Failed to index sections: {exc}") from exc

    connections_payload = None
    try:
        _stage("linking")
        from services.connection_service import connect_note
        connections = await connect_note(index_rel_path, workspace_path=workspace_path)
        connections_payload = connections.model_dump()
    except Exception as exc:
        logger.warning("Smart Connect after section split failed: %s", exc)

    return {
        "path": index_rel_path,
        "title": title,
        "folder": target_folder,
        "source": str(source_path),
        "size": total_size,
        "sections": len(sections),
        "connections": connections_payload,
    }


# Backwards-compatible thin wrapper kept so existing tests/imports work.
async def _emit_pdf_sections(
    *,
    title: str,
    source_path: Path,
    target_folder: str,
    workspace_path: Optional[Path],
    sections: List[_DocumentSection],
    job_id: Optional[str],
) -> Dict:
    return await _emit_document_sections(
        doc_type="pdf",
        title=title,
        source_path=source_path,
        target_folder=target_folder,
        workspace_path=workspace_path,
        sections=sections,
        job_id=job_id,
    )


async def fast_ingest(
    file_path: Path,
    target_folder: str = "knowledge",
    workspace_path: Optional[Path] = None,
    original_name: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Dict:
    """Import a file into memory without AI."""
    from services import ingest_jobs

    def _stage(name: str) -> None:
        if job_id:
            ingest_jobs.update_stage(job_id, name)

    if not file_path.exists():
        raise IngestError(f"File not found: {file_path}")

    display_name = original_name or file_path.name
    ext = Path(display_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IngestError(f"Unsupported file type: {ext}")

    title = Path(display_name).stem
    mem = _memory_dir(workspace_path)
    folder = mem / target_folder
    folder.mkdir(parents=True, exist_ok=True)

    if ext == ".md":
        content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        if not content.strip().startswith("---"):
            content = _make_frontmatter(title, str(file_path)) + content

        # Step 27d — split long markdown documents on top-level headings.
        # Only the body (after frontmatter) is fed into the detector so we
        # don't pick up pseudo-headings inside YAML.
        from utils.markdown import parse_frontmatter
        _fm, md_body = parse_frontmatter(content)
        if len(md_body) >= SECTION_SPLIT_MIN_CHARS:
            md_sections = _detect_markdown_sections(md_body)
            if len(md_sections) >= SECTION_SPLIT_MIN_HEADINGS:
                _stage("splitting")
                return await _emit_document_sections(
                    doc_type="markdown",
                    title=title,
                    source_path=file_path,
                    target_folder=target_folder,
                    workspace_path=workspace_path,
                    sections=md_sections,
                    job_id=job_id,
                )

        target = _unique_path(folder / display_name)
        await asyncio.to_thread(target.write_text, content, encoding="utf-8")

    elif ext == ".txt":
        content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")

        # Step 27d — long plain-text imports get the same heading-based
        # split as PDFs (notes, reports, copy-pasted papers).
        if len(content) >= SECTION_SPLIT_MIN_CHARS:
            txt_sections = _detect_pdf_sections(content)
            if len(txt_sections) >= SECTION_SPLIT_MIN_HEADINGS:
                _stage("splitting")
                return await _emit_document_sections(
                    doc_type="text",
                    title=title,
                    source_path=file_path,
                    target_folder=target_folder,
                    workspace_path=workspace_path,
                    sections=txt_sections,
                    job_id=job_id,
                )

        md_name = f"{_slugify(title)}.md"
        fm = _make_frontmatter(title, str(file_path))
        target = _unique_path(folder / md_name)
        await asyncio.to_thread(target.write_text, fm + content, encoding="utf-8")

    elif ext == ".pdf":
        # pdfplumber is fully synchronous and CPU-heavy on big PDFs (200 MB+).
        # Without to_thread it blocks the FastAPI event loop, which is why
        # /api/memory/ingest/status polls were stacking up as 'pending'.
        _stage("extracting")
        text = await asyncio.to_thread(_extract_pdf_text, file_path)

        # Step 27a — split long PDFs with enough headings into per-section
        # notes so the graph sees them as a cluster of related notes rather
        # than a single hub. Below either threshold the existing single-
        # file path runs unchanged (memos, short reports stay one file).
        sections = _detect_pdf_sections(text) if len(text) >= SECTION_SPLIT_MIN_CHARS else []
        if len(sections) >= SECTION_SPLIT_MIN_HEADINGS:
            _stage("splitting")
            return await _emit_document_sections(
                doc_type="pdf",
                title=title,
                source_path=file_path,
                target_folder=target_folder,
                workspace_path=workspace_path,
                sections=sections,
                job_id=job_id,
            )

        md_name = f"{_slugify(title)}.md"
        fm = _make_frontmatter(title, str(file_path))
        target = _unique_path(folder / md_name)
        await asyncio.to_thread(target.write_text, fm + text, encoding="utf-8")

    elif ext == ".json":
        # Pretty-print JSON inside a fenced code block so it stays readable
        # in the markdown viewer and remains greppable. Invalid JSON is
        # preserved verbatim so the user doesn't lose data.
        raw = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        try:
            parsed = json.loads(raw)
            body = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as exc:
            logger.warning("JSON ingest: invalid JSON in %s (%s) — keeping raw text", file_path.name, exc)
            parsed = None
            body = raw

        # Step 27d — split large JSON files into per-key (dict) or per-chunk
        # (list) sections. Each section keeps its original structure inside
        # a fenced ```json``` block so values remain valid and greppable.
        if parsed is not None and len(raw) >= SECTION_SPLIT_MIN_CHARS:
            json_sections = _detect_json_sections(parsed)
            if len(json_sections) >= SECTION_SPLIT_MIN_HEADINGS:
                _stage("splitting")
                return await _emit_document_sections(
                    doc_type="json",
                    title=title,
                    source_path=file_path,
                    target_folder=target_folder,
                    workspace_path=workspace_path,
                    sections=json_sections,
                    job_id=job_id,
                )

        md_name = f"{_slugify(title)}.md"
        fm = _make_frontmatter(title, str(file_path), tags=["imported", "json"])
        content = f"{fm}```json\n{body}\n```\n"
        target = _unique_path(folder / md_name)
        await asyncio.to_thread(target.write_text, content, encoding="utf-8")

    elif ext in (".csv", ".xml"):
        from services.structured_ingest import ingest_structured_file
        result = await ingest_structured_file(
            file_path,
            target_folder=target_folder,
            workspace_path=workspace_path,
            original_name=display_name,
        )
        # Structured ingest handles its own indexing and graph rebuild
        return result

    else:
        raise IngestError(f"Unsupported: {ext}")

    rel_path = target.relative_to(mem).as_posix()

    # Capture size BEFORE the long-running indexing / Smart Connect phases.
    # Doing it here (a) keeps the sync stat() off the hot async path,
    # (b) avoids FileNotFoundError if the file is moved/replaced/deleted
    # by a concurrent process (e.g. reset script, manual edit, another
    # ingest hitting the same target name).
    try:
        target_size = await asyncio.to_thread(lambda: target.stat().st_size)
    except FileNotFoundError:
        target_size = 0

    from services.memory_service import index_note_file
    try:
        _stage("indexing")
        await index_note_file(rel_path, workspace_path=workspace_path)
    except Exception as exc:
        # Best-effort cleanup; the file may already be gone.
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        raise IngestError(f"Failed to index note: {exc}") from exc

    # Step 25 — Smart Connect: per-note linking + incremental graph update.
    # Replaces the previous full ``rebuild_graph()`` call which scaled poorly.
    # Full rebuilds remain available for batch imports and the manual
    # "Reindex all" / "Repair graph" actions.
    connections_payload = None
    try:
        _stage("linking")
        from services.connection_service import connect_note
        connections = await connect_note(rel_path, workspace_path=workspace_path)
        connections_payload = connections.model_dump()
    except Exception as exc:
        logger.warning("Smart Connect after ingest failed: %s", exc)

    return {
        "path": rel_path,
        "title": title,
        "folder": target_folder,
        "source": str(file_path),
        "size": target_size,
        "connections": connections_payload,
    }


async def smart_enrich(
    note_path: str,
    api_key: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    """Use Claude to enhance a note with summary and tags."""
    import anthropic
    from services.memory_service import _validate_path
    from services.privacy import assert_provider_allowed, PrivacyBlockedError

    try:
        assert_provider_allowed("anthropic", workspace_path)
    except PrivacyBlockedError as exc:
        raise IngestError(str(exc)) from exc

    mem = _memory_dir(workspace_path)
    _validate_path(note_path, mem)
    full_path = mem / note_path
    if not full_path.exists():
        raise IngestError(f"Note not found: {note_path}")

    content = full_path.read_text(encoding="utf-8")
    truncated = content[:3000]

    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Analyze this note and return JSON with: summary (1-2 sentences), tags (list of 3-5 keywords).\n\nNote:\n{truncated}\n\nReturn only valid JSON.",
        }],
    )

    text = response.content[0].text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"summary": text[:200], "tags": []}

    # Update frontmatter
    from utils.markdown import parse_frontmatter
    fm, body = parse_frontmatter(content)
    fm["summary"] = data.get("summary", "")
    existing_tags = fm.get("tags", [])
    new_tags = data.get("tags", [])
    fm["tags"] = list(set(existing_tags + new_tags))

    # Rebuild file using safe YAML serialization
    from utils.markdown import add_frontmatter as _add_fm
    full_path.write_text(_add_fm(body, fm), encoding="utf-8")

    return {
        "path": note_path,
        "summary": data.get("summary", ""),
        "tags": fm["tags"],
        "enriched": True,
    }
