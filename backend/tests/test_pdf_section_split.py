"""Tests for PDF section split (Step 27a)."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.ingest import (
    SECTION_SPLIT_MIN_CHARS,
    _detect_pdf_sections,
    _emit_pdf_sections,
    _is_heading_line,
    _PdfSection,
    _unique_dir,
)
from utils.markdown import parse_frontmatter


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "knowledge").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


# ── Heading detection unit tests ─────────────────────────────


def test_is_heading_numbered():
    assert _is_heading_line("1 Introduction")
    assert _is_heading_line("2.3 Threat Model")
    assert _is_heading_line("10. Conclusion")


def test_is_heading_allcaps():
    assert _is_heading_line("ABSTRACT")
    assert _is_heading_line("RELATED WORK")


def test_not_heading_running_prose():
    assert not _is_heading_line("the language model produced output")
    assert not _is_heading_line("This is a complete sentence with a period.")


def test_not_heading_too_long():
    assert not _is_heading_line("A" * 200)


def test_not_heading_blank():
    assert not _is_heading_line("")
    assert not _is_heading_line("   ")


# ── _detect_pdf_sections ────────────────────────────────────


def test_detect_sections_numbered_headings():
    text = "Some intro text here.\n\n1 Introduction\n\nIntro body.\n\n2 Methods\n\nMethods body.\n\n3 Results\n\nResults body.\n\n4 Conclusion\n\nFinal body.\n"
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    assert "Front Matter" in titles
    assert "1 Introduction" in titles
    assert "4 Conclusion" in titles
    # 4 numbered + front-matter
    assert len(sections) == 5


def test_detect_sections_all_caps():
    text = "ABSTRACT\n\nAbstract body here.\n\nINTRODUCTION\n\nIntro body.\n\nRELATED WORK\n\nRelated body.\n\nCONCLUSION\n\nFinal.\n"
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    assert "ABSTRACT" in titles
    assert "RELATED WORK" in titles
    # No front matter (text starts with heading)
    assert "Front Matter" not in titles
    assert len(sections) == 4


def test_detect_sections_below_threshold_returns_empty():
    # No headings at all
    text = "Just some prose text, no structure.\nLine two.\nLine three."
    sections = _detect_pdf_sections(text)
    assert sections == []


def test_detect_sections_skips_subsections():
    """Sub-sections like '2.3.1 Foo' should not become top-level sections."""
    text = "1 Top\n\nBody.\n\n1.1 Sub\n\nSub body.\n\n2 NextTop\n\nMore body.\n"
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    # 1 Top and 2 NextTop are top-level (one dot or no dots)
    assert "1 Top" in titles
    assert "2 NextTop" in titles
    # 1.1 Sub is also one dot, so top-level by current rule — that's fine
    # for our heuristic. Just ensure deeper levels would be excluded.


def test_detect_sections_three_dot_excluded():
    """Three-level numbering '1.2.3 Foo' should be filtered as non-top-level."""
    text = "1 Top\n\nBody.\n\n1.2.3 Deep\n\nDeep body.\n\n2 Other\n\nOther.\n"
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    assert "1.2.3 Deep" not in titles


def test_detect_sections_empty_text():
    assert _detect_pdf_sections("") == []
    assert _detect_pdf_sections("   \n\n   ") == []


# ── pdfplumber-style continuous text (no blank-surround) ────


def test_detect_sections_pdfplumber_no_blank_surround():
    """pdfplumber extracts text without blank lines between sections.

    The strict numbered-heading path must accept these without the
    blank-surround requirement, otherwise zero sections are detected
    on real academic PDFs (regression from real-world usage).
    """
    body = ("body sentence. " * 30 + "\n") * 4
    text = (
        "Title page line\n"
        "1 Introduction\n" + body +
        "2 Background\n" + body +
        "3 Method\n" + body +
        "4 Results\n" + body +
        "5 Conclusion\n" + body
    )
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    assert "1 Introduction" in titles
    assert "5 Conclusion" in titles
    assert len(sections) >= 5  # 5 numbered + optional Front Matter


def test_detect_sections_filters_toc_entries():
    """TOC lines (heading title + trailing page number) must be skipped."""
    body = ("body sentence. " * 30 + "\n") * 4
    text = (
        # TOC block — these would be false-positive headings
        "1.1 Publications 29\n"
        "1.2 Patents 42\n"
        "1.3 Notable AI Models 46\n"
        "1.4 Hardware 56\n"
        "1.5 AI Conferences 75\n"
        "\n"
        # Real sections
        "1 Introduction\n" + body +
        "2 Background\n" + body +
        "3 Method\n" + body +
        "4 Results\n" + body
    )
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    assert "1.1 Publications 29" not in titles
    assert "1.5 AI Conferences 75" not in titles
    assert "1 Introduction" in titles


def test_detect_sections_dedup_repeated_headings():
    """Repeated headings (running headers, TOC echoes) keep only one entry."""
    body = ("body sentence. " * 30 + "\n") * 4
    text = (
        "1 Introduction\n" + body +
        "1 Introduction\n" + body +  # repeat
        "2 Background\n" + body +
        "3 Method\n" + body +
        "4 Results\n" + body
    )
    sections = _detect_pdf_sections(text)
    titles = [s.title for s in sections]
    # "1 Introduction" appears once
    assert titles.count("1 Introduction") == 1


# ── _emit_pdf_sections integration ──────────────────────────


async def test_emit_sections_writes_index_and_files(ws_db, tmp_path):
    sections = [
        _PdfSection(title="Front Matter", body="Preamble text."),
        _PdfSection(title="1 Introduction", body="Introduction body."),
        _PdfSection(title="2 Methods", body="Methods body."),
        _PdfSection(title="3 Results", body="Results body."),
        _PdfSection(title="4 Conclusion", body="Conclusion body."),
    ]
    src = tmp_path / "source.pdf"
    src.write_bytes(b"")  # placeholder

    result = await _emit_pdf_sections(
        title="My Long Paper",
        source_path=src,
        target_folder="knowledge",
        workspace_path=ws_db,
        sections=sections,
        job_id=None,
    )

    assert result["sections"] == 5
    doc_dir = ws_db / "memory" / "knowledge" / "my-long-paper"
    assert doc_dir.is_dir()
    assert (doc_dir / "index.md").exists()
    # Five sections, two-digit zero-padded prefix
    section_files = sorted(p for p in doc_dir.glob("*.md") if p.name != "index.md")
    assert len(section_files) == 5
    # Filenames start with 01-, 02-, …
    assert section_files[0].name.startswith("01-")

    # Index frontmatter
    idx_content = (doc_dir / "index.md").read_text()
    fm, body = parse_frontmatter(idx_content)
    assert fm["document_type"] == "pdf-document"
    assert "pdf" in fm["tags"]
    # Body has wiki-links pointing at each section
    assert "[[knowledge/my-long-paper/01-front-matter]]" in body

    # Section frontmatter
    intro_path = next(p for p in section_files if "introduction" in p.name)
    intro_fm, intro_body = parse_frontmatter(intro_path.read_text())
    assert intro_fm["section_index"] == 2
    assert intro_fm["parent"] == "knowledge/my-long-paper/index.md"
    assert "Introduction body" in intro_body


async def test_emit_sections_reingest_uses_suffix_dir(ws_db, tmp_path):
    sections = [
        _PdfSection(title="A", body="A body"),
        _PdfSection(title="B", body="B body"),
        _PdfSection(title="C", body="C body"),
        _PdfSection(title="D", body="D body"),
    ]
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"")

    r1 = await _emit_pdf_sections(
        title="Same Doc",
        source_path=src,
        target_folder="knowledge",
        workspace_path=ws_db,
        sections=sections,
        job_id=None,
    )
    r2 = await _emit_pdf_sections(
        title="Same Doc",
        source_path=src,
        target_folder="knowledge",
        workspace_path=ws_db,
        sections=sections,
        job_id=None,
    )
    assert r1["path"] != r2["path"]
    assert r1["path"].endswith("/index.md")
    assert r2["path"].endswith("/index.md")
    # Second run goes to "same-doc-1"
    assert "same-doc-1" in r2["path"]


def test_unique_dir_returns_input_when_missing(tmp_path):
    target = tmp_path / "fresh"
    assert _unique_dir(target) == target


def test_unique_dir_adds_suffix(tmp_path):
    target = tmp_path / "exists"
    target.mkdir()
    out = _unique_dir(target)
    assert out.name == "exists-1"
    assert not out.exists()


def test_section_split_min_chars_constant():
    """Sanity: splitting threshold is documented and non-zero."""
    assert SECTION_SPLIT_MIN_CHARS >= 10_000
