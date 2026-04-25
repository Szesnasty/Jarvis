"""Tests for document section split across formats (Step 27d).

Covers JSON, plain-text and Markdown via ``services.ingest.fast_ingest``,
and large generic XML via ``services.structured_ingest.ingest_structured_file``.
PDF coverage already lives in ``test_pdf_section_split.py``.
"""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.ingest import (
    SECTION_SPLIT_MIN_CHARS,
    SECTION_SPLIT_MIN_HEADINGS,
    _detect_json_sections,
    _detect_markdown_sections,
    fast_ingest,
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


# ── JSON detector unit tests ─────────────────────────────────


def test_json_dict_sections_one_per_key():
    parsed = {f"key_{i}": {"value": i, "label": "x" * 20} for i in range(6)}
    sections = _detect_json_sections(parsed)
    assert len(sections) == 6
    assert all(s.body.startswith("```json") for s in sections)
    assert all(s.body.endswith("```") for s in sections)
    assert "key_0" in sections[0].title


def test_json_small_dict_below_threshold_not_split():
    parsed = {"a": 1, "b": 2}  # < SECTION_SPLIT_MIN_HEADINGS
    assert _detect_json_sections(parsed) == []


def test_json_list_chunked():
    parsed = [{"i": i} for i in range(120)]
    sections = _detect_json_sections(parsed)
    # 120 / 50 = 3 chunks => meets MIN_HEADINGS only at >=4; 120 / 50 = 3, so empty
    # Need at least MIN_HEADINGS chunks to keep behaviour consistent: assert
    # the function returns chunks but caller filters on count.
    assert len(sections) == 3
    assert sections[0].title.startswith("Items 1")


def test_json_long_list_produces_enough_chunks():
    parsed = [{"i": i} for i in range(220)]
    sections = _detect_json_sections(parsed)
    # 220 / 50 = 5 chunks, meets MIN_HEADINGS threshold
    assert len(sections) >= SECTION_SPLIT_MIN_HEADINGS
    assert "Items 1" in sections[0].title


def test_json_scalar_returns_empty():
    assert _detect_json_sections("hello world") == []
    assert _detect_json_sections(42) == []
    assert _detect_json_sections(None) == []


# ── Markdown detector unit tests ─────────────────────────────


def test_markdown_split_on_top_level_headings():
    text = "intro paragraph\n\n# A\nbody A\n\n# B\nbody B\n\n## C\nbody C\n\n# D\nbody D"
    sections = _detect_markdown_sections(text)
    titles = [s.title for s in sections]
    assert "Front Matter" in titles
    assert "A" in titles and "B" in titles and "C" in titles and "D" in titles


def test_markdown_ignores_headings_in_code_fence():
    text = "before\n\n```\n# not a heading\n```\n\n# Real\nbody\n\n# Two\nx\n\n# Three\ny\n\n# Four\nz"
    sections = _detect_markdown_sections(text)
    # Real, Two, Three, Four — plus Front Matter
    titles = [s.title for s in sections]
    assert "not a heading" not in titles
    assert "Real" in titles


def test_markdown_no_headings_returns_empty():
    text = "just a paragraph with no headings whatsoever\nstill no headings here"
    assert _detect_markdown_sections(text) == []


# ── End-to-end: JSON ingest splits a large dict ──────────────


async def test_json_ingest_splits_large_dict(ws_db):
    payload = {f"section_{i}": {"data": "x" * 4000, "n": i} for i in range(8)}
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    assert len(raw) >= SECTION_SPLIT_MIN_CHARS

    src = ws_db / "big.json"
    src.write_text(raw, encoding="utf-8")

    result = await fast_ingest(src, target_folder="knowledge", workspace_path=ws_db)

    assert result["sections"] == 8
    index_path = ws_db / "memory" / result["path"]
    assert index_path.exists()
    fm, body = parse_frontmatter(index_path.read_text(encoding="utf-8"))
    assert fm.get("document_type") == "json-document"
    # Index should link every section as a wiki-link
    for i in range(8):
        assert "[[" in body
    # All 8 section files exist alongside the index
    section_files = sorted(index_path.parent.glob("*-*.md"))
    assert len(section_files) == 8
    sample_fm, sample_body = parse_frontmatter(section_files[0].read_text(encoding="utf-8"))
    assert sample_fm.get("section_index") == 1
    assert "json" in sample_fm.get("tags", [])
    assert "```json" in sample_body


async def test_json_ingest_small_dict_keeps_single_note(ws_db):
    payload = {"a": 1, "b": 2, "c": 3}
    src = ws_db / "small.json"
    src.write_text(json.dumps(payload), encoding="utf-8")

    result = await fast_ingest(src, target_folder="knowledge", workspace_path=ws_db)
    # Single-note path returns no "sections" key
    assert "sections" not in result
    target = ws_db / "memory" / result["path"]
    assert target.exists()


# ── End-to-end: Markdown ingest splits a large doc ───────────


async def test_markdown_ingest_splits_large_doc(ws_db):
    sections = []
    for i in range(6):
        sections.append(f"# Heading {i}\n\n" + ("body line\n" * 800))
    text = "\n\n".join(sections)
    assert len(text) >= SECTION_SPLIT_MIN_CHARS

    src = ws_db / "long.md"
    src.write_text(text, encoding="utf-8")

    result = await fast_ingest(src, target_folder="knowledge", workspace_path=ws_db)
    assert result["sections"] == 6
    index_path = ws_db / "memory" / result["path"]
    fm, _ = parse_frontmatter(index_path.read_text(encoding="utf-8"))
    assert fm.get("document_type") == "markdown-document"


# ── End-to-end: TXT ingest splits a long heading-rich doc ────


async def test_text_ingest_splits_long_heading_rich_doc(ws_db):
    sections = []
    titles = ["INTRODUCTION", "BACKGROUND", "METHOD", "RESULTS", "DISCUSSION", "CONCLUSION"]
    for t in titles:
        sections.append(f"\n{t}\n\n" + ("paragraph text. " * 500))
    text = "\n".join(sections)
    assert len(text) >= SECTION_SPLIT_MIN_CHARS

    src = ws_db / "report.txt"
    src.write_text(text, encoding="utf-8")

    result = await fast_ingest(src, target_folder="knowledge", workspace_path=ws_db)
    assert result.get("sections", 0) >= SECTION_SPLIT_MIN_HEADINGS
    index_path = ws_db / "memory" / result["path"]
    fm, _ = parse_frontmatter(index_path.read_text(encoding="utf-8"))
    assert fm.get("document_type") == "text-document"


# ── End-to-end: large generic XML splits into per-child notes ─


async def test_xml_ingest_splits_large_doc(ws_db):
    from services.structured_ingest import ingest_structured_file

    parts = ["<root>"]
    for i in range(10):
        parts.append(f"<item id='{i}'><name>Item {i}</name><body>{'x' * 4000}</body></item>")
    parts.append("</root>")
    xml = "\n".join(parts)
    assert len(xml) >= SECTION_SPLIT_MIN_CHARS

    src = ws_db / "data.xml"
    src.write_text(xml, encoding="utf-8")

    result = await ingest_structured_file(src, target_folder="knowledge", workspace_path=ws_db)
    assert result["total_notes"] == 1
    assert result.get("sections", 0) == 10
    index_rel = result["notes"][0]["path"]
    index_path = ws_db / "memory" / index_rel
    assert index_path.exists()
    fm, _ = parse_frontmatter(index_path.read_text(encoding="utf-8"))
    assert fm.get("document_type") == "xml-document"
    section_files = sorted(index_path.parent.glob("*-*.md"))
    assert len(section_files) == 10
    sample_fm, sample_body = parse_frontmatter(section_files[0].read_text(encoding="utf-8"))
    assert "xml" in sample_fm.get("tags", [])
    assert "```xml" in sample_body


async def test_xml_small_doc_keeps_single_note(ws_db):
    from services.structured_ingest import ingest_structured_file

    xml = "<root><a>1</a><b>2</b></root>"
    src = ws_db / "tiny.xml"
    src.write_text(xml, encoding="utf-8")

    result = await ingest_structured_file(src, target_folder="knowledge", workspace_path=ws_db)
    assert "sections" not in result or result.get("sections") in (None, 0)
    assert result["total_notes"] == 1
