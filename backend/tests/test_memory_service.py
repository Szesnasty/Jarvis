import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param
from services.memory_service import (
    NoteExistsError,
    NoteNotFoundError,
    create_note,
    delete_note,
    get_note,
    list_notes,
    reindex_all,
)
from utils.markdown import parse_frontmatter


@pytest.fixture
def ws(tmp_path):
    """Create a minimal workspace structure."""
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    """Workspace with initialized DB."""
    await init_database(ws / "app" / "jarvis.db")
    return ws


SAMPLE_CONTENT = "---\ntitle: Test Note\ntags: [python, testing]\n---\n\nThis is a test note about python programming."




@pytest.mark.anyio
async def test_create_note_creates_file(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    assert (ws_db / "memory" / "inbox" / "test.md").exists()




@pytest.mark.anyio
async def test_create_note_has_yaml_frontmatter(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    content = (ws_db / "memory" / "inbox" / "test.md").read_text()
    fm, body = parse_frontmatter(content)
    assert fm["title"] == "Test Note"
    assert "python" in fm["tags"]
    assert "created_at" in fm




@pytest.mark.anyio
async def test_create_note_body_content(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    content = (ws_db / "memory" / "inbox" / "test.md").read_text()
    fm, body = parse_frontmatter(content)
    assert "python programming" in body




@pytest.mark.anyio
async def test_create_note_indexed_in_sqlite(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert len(notes) == 1
    assert notes[0]["path"] == "inbox/test.md"




@pytest.mark.anyio
async def test_create_note_in_subfolder(ws_db):
    await create_note("projects/deep/nested.md", SAMPLE_CONTENT, ws_db)
    assert (ws_db / "memory" / "projects" / "deep" / "nested.md").exists()




@pytest.mark.anyio
async def test_create_note_duplicate_path_raises(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    with pytest.raises(NoteExistsError):
        await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)




@pytest.mark.anyio
async def test_list_notes_empty(ws_db):
    notes = await list_notes(workspace_path=ws_db)
    assert notes == []




@pytest.mark.anyio
async def test_list_notes_returns_all(ws_db):
    for i in range(3):
        await create_note(f"inbox/note{i}.md", f"---\ntitle: Note {i}\n---\n\nContent {i}", ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert len(notes) == 3




@pytest.mark.anyio
async def test_list_notes_by_folder(ws_db):
    await create_note("inbox/a.md", "---\ntitle: A\n---\n\nA", ws_db)
    await create_note("projects/b.md", "---\ntitle: B\n---\n\nB", ws_db)
    notes = await list_notes(folder="inbox", workspace_path=ws_db)
    assert len(notes) == 1
    assert notes[0]["folder"] == "inbox"


# Step 28b — document grouping fields surfaced from frontmatter ─────────


@pytest.mark.anyio
async def test_list_notes_exposes_document_type(ws_db):
    """Index notes from PDF section split carry document_type=pdf-document."""
    index_md = (
        "---\n"
        "title: HAI AI Index Report 2025\n"
        "document_type: pdf-document\n"
        "tags: [imported, pdf]\n"
        "---\n\n"
        "1. [[hai-ai-index/01-introduction]]\n"
    )
    await create_note("knowledge/hai-ai-index/index.md", index_md, ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert len(notes) == 1
    assert notes[0]["document_type"] == "pdf-document"
    assert notes[0]["parent"] is None
    assert notes[0]["section_index"] is None


@pytest.mark.anyio
async def test_list_notes_exposes_parent_and_section_index(ws_db):
    """Section notes carry parent + section_index from frontmatter."""
    section_md = (
        "---\n"
        "title: Introduction\n"
        "parent: knowledge/hai-ai-index/index.md\n"
        "section_index: 2\n"
        "---\n\n"
        "Body of the introduction section.\n"
    )
    await create_note("knowledge/hai-ai-index/01-introduction.md", section_md, ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert len(notes) == 1
    assert notes[0]["parent"] == "knowledge/hai-ai-index/index.md"
    assert notes[0]["section_index"] == 2
    assert notes[0]["document_type"] is None


@pytest.mark.anyio
async def test_list_notes_missing_fields_default_to_none(ws_db):
    """A plain note without grouping fields still lists with None values."""
    await create_note("inbox/plain.md", SAMPLE_CONTENT, ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert notes[0]["document_type"] is None
    assert notes[0]["parent"] is None
    assert notes[0]["section_index"] is None




@pytest.mark.anyio
async def test_list_notes_metadata_fields(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    notes = await list_notes(workspace_path=ws_db)
    note = notes[0]
    assert "title" in note
    assert "path" in note
    assert "tags" in note
    assert "updated_at" in note




@pytest.mark.anyio
async def test_search_fts5_finds_match(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    notes = await list_notes(search="python", workspace_path=ws_db)
    assert len(notes) >= 1




@pytest.mark.anyio
async def test_search_fts5_no_match(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    notes = await list_notes(search="xyznonexistent", workspace_path=ws_db)
    assert notes == []




@pytest.mark.anyio
async def test_search_fts5_partial_word(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    notes = await list_notes(search="pyth", workspace_path=ws_db)
    assert len(notes) >= 1




@pytest.mark.anyio
async def test_get_note_content(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    note = await get_note("inbox/test.md", ws_db)
    assert "python programming" in note["content"]
    assert note["title"] == "Test Note"




@pytest.mark.anyio
async def test_get_note_nonexistent_raises(ws_db):
    with pytest.raises(NoteNotFoundError):
        await get_note("inbox/nope.md", ws_db)




@pytest.mark.anyio
async def test_delete_note_moves_to_trash(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    await delete_note("inbox/test.md", ws_db)
    assert not (ws_db / "memory" / "inbox" / "test.md").exists()
    assert (ws_db / ".trash" / "inbox" / "test.md").exists()




@pytest.mark.anyio
async def test_delete_note_removes_from_index(ws_db):
    await create_note("inbox/test.md", SAMPLE_CONTENT, ws_db)
    await delete_note("inbox/test.md", ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert len(notes) == 0
