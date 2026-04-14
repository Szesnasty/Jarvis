import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.memory_service import create_note, list_notes


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


TITLE_MATCH = "---\ntitle: Vacation Plans 2025\ntags: [travel]\n---\n\nDetailed vacation plans for summer."
BODY_ONLY = "---\ntitle: Daily Notes\ntags: [daily]\n---\n\nToday I thought about vacation briefly while doing other things."
OLD_RELEVANT = "---\ntitle: Travel Guide\ntags: [travel, planning]\ncreated_at: '2024-01-01'\nupdated_at: '2024-01-01'\n---\n\nComplete travel vacation guide with tips for vacation planning."
NEW_IRRELEVANT = "---\ntitle: Grocery List\ntags: [shopping]\nupdated_at: '2026-04-14'\n---\n\nBuy milk, eggs, bread. Also mentioned vacation once."


@pytest.mark.anyio
async def test_title_match_ranks_higher_than_body(ws_db):
    """Note with search term in title should outrank body-only match."""
    await create_note("notes/body-only.md", BODY_ONLY, ws_db)
    await create_note("notes/title-match.md", TITLE_MATCH, ws_db)

    results = await list_notes(search="vacation", workspace_path=ws_db)
    assert len(results) >= 2
    # Title match should be first
    assert results[0]["path"] == "notes/title-match.md"


@pytest.mark.anyio
async def test_bm25_order_not_date_order(ws_db):
    """Old but relevant note should outrank new but tangential note."""
    await create_note("notes/new-irrelevant.md", NEW_IRRELEVANT, ws_db)
    await create_note("notes/old-relevant.md", OLD_RELEVANT, ws_db)

    results = await list_notes(search="vacation planning", workspace_path=ws_db)
    assert len(results) >= 2
    # Old relevant note should rank first (has vacation + planning in title and body)
    paths = [r["path"] for r in results]
    old_idx = paths.index("notes/old-relevant.md")
    new_idx = paths.index("notes/new-irrelevant.md")
    assert old_idx < new_idx


@pytest.mark.anyio
async def test_bm25_score_returned(ws_db):
    """Search results include _bm25_score for downstream use."""
    await create_note("inbox/test.md", TITLE_MATCH, ws_db)

    results = await list_notes(search="vacation", workspace_path=ws_db)
    assert len(results) == 1
    assert "_bm25_score" in results[0]
    # BM25 scores are negative (lower = better)
    assert results[0]["_bm25_score"] < 0


@pytest.mark.anyio
async def test_or_fallback_when_and_too_few(ws_db):
    """If AND match returns < 3 results, OR query broadens results."""
    # Create notes that each match one of two terms
    await create_note("notes/alpha.md", "---\ntitle: Alpha\ntags: []\n---\n\nThis is about quantum physics.", ws_db)
    await create_note("notes/beta.md", "---\ntitle: Beta\ntags: []\n---\n\nThis is about molecular biology.", ws_db)

    # AND search: "quantum biology" — no note has both words
    results = await list_notes(search="quantum biology", workspace_path=ws_db)
    # OR fallback should kick in and return both
    assert len(results) == 2


@pytest.mark.anyio
async def test_no_bm25_score_without_search(ws_db):
    """Non-search results should not have _bm25_score."""
    await create_note("inbox/test.md", TITLE_MATCH, ws_db)

    results = await list_notes(workspace_path=ws_db)
    assert len(results) == 1
    assert "_bm25_score" not in results[0]


@pytest.mark.anyio
async def test_search_with_folder_filter(ws_db):
    """BM25 ranking works with folder filter."""
    await create_note("inbox/a.md", TITLE_MATCH, ws_db)
    await create_note("projects/b.md", "---\ntitle: Vacation Project\ntags: []\n---\n\nVacation project.", ws_db)

    results = await list_notes(search="vacation", folder="inbox", workspace_path=ws_db)
    assert len(results) == 1
    assert results[0]["folder"] == "inbox"
