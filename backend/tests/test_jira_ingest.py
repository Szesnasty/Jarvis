"""Tests for services.jira_ingest (step 22a)."""

from pathlib import Path

import aiosqlite
import pytest

from services.jira_ingest import (
    JiraImportError,
    _parse_sprint_string,
    build_markdown,
    iter_xml_issues,
    list_imports,
    list_issues,
    run_import,
)

pytestmark = pytest.mark.anyio(backends=["asyncio"])

FIXTURES = Path(__file__).parent / "fixtures" / "jira"


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


# ────────────────────────────────────────────────────────────────────
# XML ingest
# ────────────────────────────────────────────────────────────────────


async def test_xml_ingest_small(ws: Path):
    stats = await run_import(FIXTURES / "small.xml", workspace_path=ws)

    assert stats.issue_count == 5
    assert stats.inserted == 5
    assert stats.updated == 0
    assert stats.skipped == 0
    assert sorted(stats.project_keys) == ["AUTH", "ONB"]

    db_path = ws / "app" / "jarvis.db"
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row

        row = await (await db.execute(
            "SELECT * FROM issues WHERE issue_key = ?", ("ONB-142",)
        )).fetchone()
        assert row is not None
        assert row["project_key"] == "ONB"
        assert row["status"] == "In Progress"
        assert row["status_category"] == "in-progress"
        assert row["priority"] == "High"
        assert row["assignee"] == "michal.kowalski"
        assert row["epic_key"] == "ONB-100"
        assert row["note_path"] == "memory/jira/ONB/ONB-142.md"

        labels = [r[0] for r in await (await db.execute(
            "SELECT label FROM issue_labels WHERE issue_key = ? ORDER BY label",
            ("ONB-142",),
        )).fetchall()]
        assert labels == ["auth", "onboarding", "session"]

        components = [r[0] for r in await (await db.execute(
            "SELECT component FROM issue_components WHERE issue_key = ? ORDER BY component",
            ("ONB-142",),
        )).fetchall()]
        assert components == ["onboarding-flow", "web-auth"]

        sprints = [tuple(r) for r in await (await db.execute(
            "SELECT sprint_name, sprint_state FROM issue_sprints WHERE issue_key = ?",
            ("ONB-142",),
        )).fetchall()]
        assert sprints == [("Onboarding Sprint 14", "active")]

        links = await (await db.execute(
            """SELECT target_key, link_type, direction FROM issue_links
               WHERE source_key = ? ORDER BY target_key""",
            ("ONB-142",),
        )).fetchall()
        link_tuples = {(r[0], r[1], r[2]) for r in links}
        assert ("ONB-150", "blocks", "outbound") in link_tuples
        assert ("AUTH-88", "is blocked by", "inbound") in link_tuples
        assert ("ONB-141", "relates to", "outbound") in link_tuples

        comments = await (await db.execute(
            "SELECT author, body FROM issue_comments WHERE issue_key = ? ORDER BY id",
            ("ONB-142",),
        )).fetchall()
        assert len(comments) == 2
        assert comments[0][0] == "anna.nowak"
        assert "reproduce" in comments[0][1].lower()


async def test_markdown_roundtrip(ws: Path):
    await run_import(FIXTURES / "small.xml", workspace_path=ws)

    md_path = ws / "memory" / "jira" / "ONB" / "ONB-142.md"
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")

    assert content.startswith("---\n")
    assert "issue_key: ONB-142" in content
    assert "project_key: ONB" in content
    assert "status: In Progress" in content
    assert "type: jira_issue" in content
    # Description converted from Jira wiki markup to Markdown.
    assert "```js" in content
    assert "## Description" in content
    assert "## Comments" in content
    assert "## Links" in content
    # Wiki-links so graph/entity extraction can pick them up.
    assert "[[ONB-100]]" in content  # epic
    assert "[[ONB-150]]" in content  # blocks
    assert "[[AUTH-88]]" in content  # blocked by

    # ONB-150 heading conversion h2. → ##
    onb150 = (ws / "memory" / "jira" / "ONB" / "ONB-150.md").read_text("utf-8")
    assert "## Acceptance criteria" in onb150

    # AUTH project gets its own folder.
    assert (ws / "memory" / "jira" / "AUTH" / "AUTH-88.md").exists()


async def test_reimport_idempotent(ws: Path):
    first = await run_import(FIXTURES / "small.xml", workspace_path=ws)
    assert first.inserted == 5

    # Record file mtimes — idempotent re-import must not rewrite them.
    md_files = list((ws / "memory" / "jira").rglob("*.md"))
    mtimes = {p: p.stat().st_mtime_ns for p in md_files}

    second = await run_import(FIXTURES / "small.xml", workspace_path=ws)
    assert second.issue_count == 5
    assert second.inserted == 0
    assert second.updated == 0
    assert second.skipped == 5

    for p, mt in mtimes.items():
        assert p.stat().st_mtime_ns == mt, f"File re-written: {p}"


async def test_field_change_triggers_update(ws: Path, tmp_path: Path):
    await run_import(FIXTURES / "small.xml", workspace_path=ws)

    # Flip one issue's status and re-import.
    mutated = tmp_path / "mutated.xml"
    original = (FIXTURES / "small.xml").read_text("utf-8")
    mutated.write_text(
        original.replace(
            "<status>In Progress</status>\n      <assignee>michal.kowalski</assignee>\n      <reporter>anna.nowak</reporter>\n      <created>Sun, 8 Mar 2026 10:11:00 +0000</created>",
            "<status>Done</status>\n      <assignee>michal.kowalski</assignee>\n      <reporter>anna.nowak</reporter>\n      <created>Sun, 8 Mar 2026 10:11:00 +0000</created>",
        ),
        encoding="utf-8",
    )

    stats = await run_import(mutated, workspace_path=ws)
    assert stats.updated == 1
    assert stats.inserted == 0
    assert stats.skipped == 4

    async with aiosqlite.connect(str(ws / "app" / "jarvis.db")) as db:
        row = await (await db.execute(
            "SELECT status, status_category FROM issues WHERE issue_key = ?",
            ("ONB-142",),
        )).fetchone()
    assert tuple(row) == ("Done", "done")


# ────────────────────────────────────────────────────────────────────
# CSV ingest
# ────────────────────────────────────────────────────────────────────


async def test_csv_duplicate_columns(ws: Path):
    stats = await run_import(FIXTURES / "export.csv", workspace_path=ws)
    assert stats.issue_count == 4
    assert stats.inserted == 4

    async with aiosqlite.connect(str(ws / "app" / "jarvis.db")) as db:
        db.row_factory = aiosqlite.Row

        # Duplicate Labels columns both captured.
        labels = [r[0] for r in await (await db.execute(
            "SELECT label FROM issue_labels WHERE issue_key = ? ORDER BY label",
            ("ONB-142",),
        )).fetchall()]
        assert "onboarding" in labels
        assert "auth" in labels

        # Both Outward and Inward Blocks columns captured as links.
        links = await (await db.execute(
            """SELECT target_key, link_type, direction FROM issue_links
               WHERE source_key = ?""",
            ("ONB-142",),
        )).fetchall()
        link_set = {(r[0], r[1], r[2]) for r in links}
        assert ("ONB-150", "blocks", "outbound") in link_set
        assert ("AUTH-88", "is blocked by", "inbound") in link_set


# ────────────────────────────────────────────────────────────────────
# Security
# ────────────────────────────────────────────────────────────────────


def test_xxe_blocked():
    with pytest.raises(Exception) as exc_info:
        list(iter_xml_issues(FIXTURES / "xxe.xml"))
    # defusedxml raises DTDForbidden / EntitiesForbidden — both acceptable.
    name = type(exc_info.value).__name__
    assert "Forbidden" in name or "DTD" in name, f"Unexpected exception: {name}"


async def test_path_traversal_blocked(ws: Path, tmp_path: Path):
    bad = tmp_path / "bad.xml"
    bad.write_text(
        '<?xml version="1.0"?><rss><channel>'
        '<item>'
        '<key>../../etc/passwd</key>'
        '<summary>evil</summary><type>Task</type><status>Open</status>'
        '<created>Mon, 1 Feb 2026 09:00:00 +0000</created>'
        '<updated>Mon, 1 Feb 2026 09:00:00 +0000</updated>'
        '</item>'
        '</channel></rss>',
        encoding="utf-8",
    )
    # Invalid key is skipped (logged), producing zero writes rather than escaping the sandbox.
    stats = await run_import(bad, workspace_path=ws)
    assert stats.issue_count == 0
    assert stats.inserted == 0
    # Absolutely no file leaked outside memory/jira.
    outside = list((ws.parent).glob("**/passwd"))
    assert outside == []


# ────────────────────────────────────────────────────────────────────
# Listing APIs
# ────────────────────────────────────────────────────────────────────


async def test_list_imports_and_issues(ws: Path):
    await run_import(FIXTURES / "small.xml", workspace_path=ws)

    imports = await list_imports(workspace_path=ws)
    assert len(imports) == 1
    assert imports[0]["status"] == "done"
    assert imports[0]["issue_count"] == 5
    assert imports[0]["inserted"] == 5
    assert sorted(imports[0]["project_keys"]) == ["AUTH", "ONB"]

    issues = await list_issues(project="ONB", workspace_path=ws)
    keys = [i["issue_key"] for i in issues]
    assert set(keys) == {"ONB-100", "ONB-141", "ONB-142", "ONB-150"}

    in_progress = await list_issues(status_category="in-progress", workspace_path=ws)
    assert {i["issue_key"] for i in in_progress} == {"ONB-142", "ONB-100", "AUTH-88"}


async def test_project_filter(ws: Path):
    stats = await run_import(
        FIXTURES / "small.xml", workspace_path=ws, project_filter=["AUTH"]
    )
    assert stats.issue_count == 1
    assert stats.inserted == 1
    assert stats.project_keys == ["AUTH"]
    assert (ws / "memory" / "jira" / "AUTH" / "AUTH-88.md").exists()
    assert not (ws / "memory" / "jira" / "ONB").exists()


# ────────────────────────────────────────────────────────────────────
# Unit-level helpers
# ────────────────────────────────────────────────────────────────────


def test_parse_sprint_string():
    s = _parse_sprint_string(
        "com.atlassian.greenhopper.service.sprint.Sprint@abc123"
        "[id=14,rapidViewId=2,state=ACTIVE,name=Onboarding Sprint 14,goal=]"
    )
    assert s is not None
    assert s.name == "Onboarding Sprint 14"
    assert s.state == "active"

    assert _parse_sprint_string("") is None
    assert _parse_sprint_string("garbage") is None


def test_build_markdown_empty_optionals():
    from services.jira_ingest import Issue

    issue = Issue(
        issue_key="X-1",
        project_key="X",
        title="Hello",
        issue_type="Task",
        status="Open",
    )
    md = build_markdown(issue)
    assert "# X-1 — Hello" in md
    assert md.startswith("---\n")
    # No optional sections when no data.
    assert "## Description" not in md
    assert "## Comments" not in md
    assert "## Links" not in md
