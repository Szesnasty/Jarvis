import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.memory_service import create_note, list_notes, reindex_all


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param
from utils.markdown import parse_frontmatter


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


SAMPLE = "---\ntitle: Reindex Test\ntags: [test]\n---\n\nBody content here."




@pytest.mark.anyio
async def test_reindex_from_empty(ws_db):
    count = await reindex_all(ws_db)
    assert count == 0




@pytest.mark.anyio
async def test_reindex_restores_after_db_delete(ws_db):
    await create_note("inbox/a.md", SAMPLE, ws_db)
    await create_note("inbox/b.md", SAMPLE.replace("Reindex Test", "Second"), ws_db)
    # Delete DB
    (ws_db / "app" / "jarvis.db").unlink()
    count = await reindex_all(ws_db)
    assert count == 2




@pytest.mark.anyio
async def test_reindex_matches_original_metadata(ws_db):
    await create_note("projects/proj.md", SAMPLE, ws_db)
    original = await list_notes(workspace_path=ws_db)
    # Delete and reindex
    (ws_db / "app" / "jarvis.db").unlink()
    await reindex_all(ws_db)
    restored = await list_notes(workspace_path=ws_db)
    assert restored[0]["title"] == original[0]["title"]
    assert restored[0]["path"] == original[0]["path"]




@pytest.mark.anyio
async def test_reindex_picks_up_manual_file(ws_db):
    # Write file directly to disk (not via service)
    (ws_db / "memory" / "inbox").mkdir(exist_ok=True)
    (ws_db / "memory" / "inbox" / "manual.md").write_text(
        "---\ntitle: Manual\n---\n\nManually created."
    )
    count = await reindex_all(ws_db)
    assert count == 1
    notes = await list_notes(workspace_path=ws_db)
    assert notes[0]["title"] == "Manual"




@pytest.mark.anyio
async def test_reindex_removes_orphaned_entries(ws_db):
    await create_note("inbox/temp.md", SAMPLE, ws_db)
    # Remove file from disk but leave DB entry
    (ws_db / "memory" / "inbox" / "temp.md").unlink()
    await reindex_all(ws_db)
    notes = await list_notes(workspace_path=ws_db)
    assert len(notes) == 0




@pytest.mark.anyio
async def test_reindex_preserves_search(ws_db):
    await create_note("inbox/a.md", "---\ntitle: Python Guide\n---\n\nPython is great.", ws_db)
    (ws_db / "app" / "jarvis.db").unlink()
    await reindex_all(ws_db)
    notes = await list_notes(search="Python", workspace_path=ws_db)
    assert len(notes) >= 1
