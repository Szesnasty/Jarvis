import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.planning_service import create_plan, get_plan, list_plans, update_plan_task
from utils.markdown import parse_frontmatter


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


@pytest.mark.anyio
async def test_create_plan_creates_file(ws_db):
    result = await create_plan("Weekly", ["Buy milk", "Call mom"], ws_db)
    assert (ws_db / "memory" / result["path"]).exists()


@pytest.mark.anyio
async def test_plan_has_date_in_filename(ws_db):
    result = await create_plan("Weekly", ["Task"], ws_db)
    import re
    assert re.match(r"plans/\d{4}-\d{2}-\d{2}-weekly\.md", result["path"])


@pytest.mark.anyio
async def test_plan_has_sections(ws_db):
    result = await create_plan("My Plan", ["A", "B"], ws_db)
    content = result["content"]
    assert "## Today" in content
    assert "## This Week" in content
    assert "## Later" in content


@pytest.mark.anyio
async def test_plan_has_checkboxes(ws_db):
    result = await create_plan("Tasks", ["Buy milk", "Call mom"], ws_db)
    content = result["content"]
    assert "- [ ] Buy milk" in content
    assert "- [ ] Call mom" in content


@pytest.mark.anyio
async def test_plan_indexed_in_sqlite(ws_db):
    from services.memory_service import list_notes

    await create_plan("Indexed Plan", ["Task"], ws_db)
    results = await list_notes(folder="plans", workspace_path=ws_db)
    assert len(results) >= 1
    assert any("plans/" in r["path"] for r in results)


@pytest.mark.anyio
async def test_update_plan_toggles_checkbox(ws_db):
    result = await create_plan("Toggle", ["A", "B", "C"], ws_db)
    updated = await update_plan_task(result["path"], 1, True, ws_db)
    assert "- [x] B" in updated
    assert "- [ ] A" in updated


@pytest.mark.anyio
async def test_update_plan_preserves_other_tasks(ws_db):
    result = await create_plan("Preserve", ["A", "B", "C"], ws_db)
    updated = await update_plan_task(result["path"], 0, True, ws_db)
    assert "- [x] A" in updated
    assert "- [ ] B" in updated
    assert "- [ ] C" in updated


@pytest.mark.anyio
async def test_list_plans_sorted_by_date(ws_db):
    await create_plan("Alpha", ["Task"], ws_db)
    await create_plan("Beta", ["Task"], ws_db)
    plans = await list_plans(ws_db)
    assert len(plans) >= 2
    # Sorted latest first (reverse alphabetical for same-day)
    paths = [p["path"] for p in plans]
    assert paths == sorted(paths, reverse=True)


@pytest.mark.anyio
async def test_list_plans_empty(ws_db):
    plans = await list_plans(ws_db)
    assert plans == []


@pytest.mark.anyio
async def test_get_plan_content(ws_db):
    result = await create_plan("Content", ["Item"], ws_db)
    content = await get_plan(result["path"], ws_db)
    assert "## Today" in content
    assert "- [ ] Item" in content


@pytest.mark.anyio
async def test_create_plan_via_tool(ws_db):
    from services.tools import execute_tool

    import json

    raw = await execute_tool(
        "create_plan",
        {"title": "Tool Plan", "items": ["X", "Y"]},
        workspace_path=ws_db,
    )
    data = json.loads(raw)
    assert "path" in data
    assert (ws_db / "memory" / data["path"]).exists()


@pytest.mark.anyio
async def test_update_plan_via_tool(ws_db):
    result = await create_plan("ToolUpdate", ["A", "B"], ws_db)
    updated = await execute_tool_update(result["path"], ws_db)
    assert "- [x] A" in updated


async def execute_tool_update(path, ws_db):
    from services.tools import execute_tool

    return await execute_tool(
        "update_plan",
        {"path": path, "task_index": 0, "checked": True},
        workspace_path=ws_db,
    )
