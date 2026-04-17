"""Tests for CSV/XML structured ingest (Jira exports)."""

import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.structured_ingest import (
    JiraIssue,
    _detect_jira_csv,
    _group_issues,
    _issue_to_row,
    parse_csv_file,
    parse_xml_file,
    ingest_structured_file,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "knowledge").mkdir()
    (tmp_path / "graph").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


# ---------------------------------------------------------------------------
# Jira CSV detection
# ---------------------------------------------------------------------------


def test_detect_jira_csv_positive():
    headers = ["Issue key", "Summary", "Status", "Issue Type", "Assignee"]
    assert _detect_jira_csv(headers) is True


def test_detect_jira_csv_negative():
    headers = ["Name", "Email", "Phone"]
    assert _detect_jira_csv(headers) is False


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


@pytest.fixture
def jira_csv(tmp_path):
    content = textwrap.dedent("""\
        Issue key,Summary,Issue Type,Status,Priority,Assignee,Reporter,Epic Link,Sprint,Labels,Components,Description
        PROJ-1,Fix login bug,Bug,Done,High,jan.kowalski,anna.nowak,PROJ-100,Sprint 5,backend,Auth,Login form crashes on submit
        PROJ-2,Add dark mode,Story,In Progress,Medium,anna.nowak,jan.kowalski,PROJ-100,Sprint 5,"frontend,ui",UI,Implement dark mode toggle
        PROJ-3,Upgrade DB,Task,To Do,Low,jan.kowalski,,PROJ-200,Sprint 6,,Infrastructure,Migrate to PostgreSQL 16
        PROJ-4,Write tests,Sub-task,Done,Medium,,,PROJ-200,Sprint 6,testing,,Add unit tests for auth module
    """)
    f = tmp_path / "jira_export.csv"
    f.write_text(content, encoding="utf-8")
    return f


def test_parse_jira_csv(jira_csv):
    headers, issues, is_jira = parse_csv_file(jira_csv)
    assert is_jira is True
    assert len(issues) == 4

    # First issue
    assert issues[0].key == "PROJ-1"
    assert issues[0].summary == "Fix login bug"
    assert issues[0].issue_type == "Bug"
    assert issues[0].status == "Done"
    assert issues[0].assignee == "jan.kowalski"
    assert issues[0].reporter == "anna.nowak"
    assert issues[0].epic == "PROJ-100"

    # Multi-value labels
    assert issues[1].labels == ["frontend", "ui"]

    # Empty fields
    assert issues[2].reporter == ""
    assert issues[3].assignee == ""


def test_parse_generic_csv(tmp_path):
    content = "Name,Email,Score\nAlice,alice@test.com,95\nBob,bob@test.com,87\n"
    f = tmp_path / "generic.csv"
    f.write_text(content)
    headers, issues, is_jira = parse_csv_file(f)
    assert is_jira is False
    assert len(issues) == 0
    assert headers == ["Name", "Email", "Score"]


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------


@pytest.fixture
def jira_xml(tmp_path):
    content = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="0.92">
          <channel>
            <title>Jira Export</title>
            <item>
              <key>PROJ-1</key>
              <summary>Fix login bug</summary>
              <type>Bug</type>
              <status>Done</status>
              <priority>High</priority>
              <assignee>jan.kowalski</assignee>
              <reporter>anna.nowak</reporter>
              <project>PROJ</project>
              <description>Login form crashes on submit</description>
              <created>2026-01-15</created>
              <updated>2026-02-01</updated>
              <component>Auth</component>
              <labels>
                <label>backend</label>
              </labels>
            </item>
            <item>
              <key>PROJ-2</key>
              <summary>Add dark mode</summary>
              <type>Story</type>
              <status>In Progress</status>
              <priority>Medium</priority>
              <assignee>anna.nowak</assignee>
              <reporter>jan.kowalski</reporter>
              <project>PROJ</project>
              <description>Implement dark mode toggle</description>
              <component>UI</component>
              <labels>
                <label>frontend</label>
                <label>ui</label>
              </labels>
            </item>
          </channel>
        </rss>
    """)
    f = tmp_path / "jira_export.xml"
    f.write_text(content, encoding="utf-8")
    return f


def test_parse_jira_xml(jira_xml):
    issues, is_jira = parse_xml_file(jira_xml)
    assert is_jira is True
    assert len(issues) == 2

    assert issues[0].key == "PROJ-1"
    assert issues[0].summary == "Fix login bug"
    assert issues[0].issue_type == "Bug"
    assert issues[0].assignee == "jan.kowalski"
    assert issues[0].project == "PROJ"
    assert issues[0].components == ["Auth"]
    assert issues[0].labels == ["backend"]

    assert issues[1].labels == ["frontend", "ui"]


def test_parse_generic_xml(tmp_path):
    content = '<?xml version="1.0"?><data><record><name>Alice</name></record></data>'
    f = tmp_path / "generic.xml"
    f.write_text(content)
    issues, is_jira = parse_xml_file(f)
    assert is_jira is False
    assert len(issues) == 0


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def test_group_issues_by_epic():
    issues = [
        JiraIssue(key="P-1", summary="A", epic="Epic-1"),
        JiraIssue(key="P-2", summary="B", epic="Epic-1"),
        JiraIssue(key="P-3", summary="C", epic="Epic-2"),
        JiraIssue(key="P-4", summary="D", epic=""),  # no epic, falls to project
    ]
    groups = _group_issues(issues)
    assert "Epic-1" in groups
    assert len(groups["Epic-1"]) == 2
    assert "Epic-2" in groups
    assert "ungrouped" in groups


# ---------------------------------------------------------------------------
# Issue to markdown
# ---------------------------------------------------------------------------


def test_issue_to_row():
    issue = JiraIssue(
        key="PROJ-1",
        summary="Fix login bug",
        issue_type="Bug",
        status="Done",
        assignee="jan.kowalski",
        description="Login crashes",
    )
    md = _issue_to_row(issue)
    assert "### PROJ-1: Fix login bug" in md
    assert "**Type:** Bug" in md
    assert "**Assignee:** jan.kowalski" in md
    assert "Login crashes" in md


# ---------------------------------------------------------------------------
# Full ingest pipeline
# ---------------------------------------------------------------------------


async def test_ingest_jira_csv(jira_csv, ws_db):
    result = await ingest_structured_file(
        jira_csv,
        target_folder="knowledge",
        workspace_path=ws_db,
        original_name="jira_export.csv",
    )
    assert result["format"] == "jira"
    assert result["total_notes"] >= 2  # overview + at least 1 group
    # Check files exist
    for note in result["notes"]:
        full_path = ws_db / "memory" / note["path"]
        assert full_path.exists()
        content = full_path.read_text()
        assert "---" in content  # has frontmatter


async def test_ingest_jira_xml(jira_xml, ws_db):
    result = await ingest_structured_file(
        jira_xml,
        target_folder="knowledge",
        workspace_path=ws_db,
        original_name="jira_export.xml",
    )
    assert result["format"] == "jira"
    assert result["total_notes"] >= 2


async def test_ingest_generic_csv(ws_db, tmp_path):
    content = "Name,Email,Score\nAlice,alice@test.com,95\nBob,bob@test.com,87\n"
    f = tmp_path / "data.csv"
    f.write_text(content)
    result = await ingest_structured_file(
        f,
        target_folder="knowledge",
        workspace_path=ws_db,
        original_name="data.csv",
    )
    assert result["format"] == "generic"
    assert result["total_notes"] == 1


async def test_ingest_generic_xml(ws_db, tmp_path):
    content = '<?xml version="1.0"?><data><record><name>Alice</name></record></data>'
    f = tmp_path / "data.xml"
    f.write_text(content)
    result = await ingest_structured_file(
        f,
        target_folder="knowledge",
        workspace_path=ws_db,
        original_name="data.xml",
    )
    assert result["format"] == "generic"
    assert result["total_notes"] == 1


async def test_ingest_large_csv(ws_db, tmp_path):
    """Test CSV with many rows to verify chunking works."""
    lines = ["Issue key,Summary,Issue Type,Status,Assignee,Epic Link"]
    for i in range(250):
        epic = f"EPIC-{i // 50}"
        lines.append(f"PROJ-{i},Task {i},Task,To Do,user{i % 5},{epic}")
    f = tmp_path / "large_jira.csv"
    f.write_text("\n".join(lines))
    result = await ingest_structured_file(
        f,
        target_folder="knowledge",
        workspace_path=ws_db,
        original_name="large_jira.csv",
    )
    assert result["format"] == "jira"
    assert result["total_notes"] >= 6  # overview + 5 epics (EPIC-0..4)


async def test_wiki_links_in_jira_notes(jira_csv, ws_db):
    """Verify that people names get wiki-linked for graph extraction."""
    result = await ingest_structured_file(
        jira_csv,
        target_folder="knowledge",
        workspace_path=ws_db,
        original_name="jira_export.csv",
    )
    # Find a group note (not overview)
    group_notes = [n for n in result["notes"] if "Overview" not in n["title"]]
    assert len(group_notes) > 0
    full_path = ws_db / "memory" / group_notes[0]["path"]
    content = full_path.read_text()
    # Should have wiki-links to people
    assert "[[" in content


# ---------------------------------------------------------------------------
# Robustness: encoding, duplicate columns, oversized fields, iterparse
# ---------------------------------------------------------------------------


def test_parse_jira_csv_with_utf8_bom(tmp_path):
    """Jira Cloud exports include a UTF-8 BOM. Detection must still work."""
    content = (
        "\ufeffIssue key,Summary,Status,Issue Type,Assignee\n"
        "PROJ-1,Crash on login,Open,Bug,jan.kowalski\n"
    )
    f = tmp_path / "bom.csv"
    f.write_bytes(content.encode("utf-8"))
    headers, issues, is_jira = parse_csv_file(f)
    assert is_jira is True
    assert headers[0] == "Issue key"  # BOM stripped
    assert len(issues) == 1
    assert issues[0].key == "PROJ-1"


def test_parse_jira_csv_with_cp1252_encoding(tmp_path):
    """Older Jira Server exports can be cp1252 — auto-detection should cope."""
    content = (
        "Issue key,Summary,Status,Issue Type,Assignee\n"
        "PROJ-1,Déjà vu — café,Open,Bug,józef\n"
    )
    f = tmp_path / "cp1252.csv"
    f.write_bytes(content.encode("cp1252"))
    _headers, issues, is_jira = parse_csv_file(f)
    assert is_jira is True
    assert len(issues) == 1
    assert "café" in issues[0].summary or "cafe" in issues[0].summary.lower()


def test_parse_jira_csv_duplicate_columns(tmp_path):
    """Jira repeats Comment / Labels columns for each value. All must survive."""
    content = (
        "Issue key,Summary,Status,Issue Type,Assignee,Labels,Labels,Comment,Comment,Comment\n"
        'PROJ-1,Bug,Open,Bug,alice,backend,urgent,"First comment","Second comment","Third comment"\n'
    )
    f = tmp_path / "dupes.csv"
    f.write_text(content)
    _headers, issues, is_jira = parse_csv_file(f)
    assert is_jira is True
    assert len(issues) == 1
    assert set(issues[0].labels) == {"backend", "urgent"}
    # All three comment cells merged together
    for expected in ("First comment", "Second comment", "Third comment"):
        assert expected in issues[0].comments


def test_parse_jira_csv_with_huge_field(tmp_path):
    """Descriptions often exceed the default csv.field_size_limit (~131 KB)."""
    big = "x" * 500_000  # 500 KB single cell
    content = (
        "Issue key,Summary,Status,Issue Type,Assignee,Description\n"
        f'PROJ-1,Bug,Open,Bug,alice,"{big}"\n'
    )
    f = tmp_path / "huge_field.csv"
    f.write_text(content)
    _headers, issues, is_jira = parse_csv_file(f)
    assert is_jira is True
    assert len(issues) == 1
    assert len(issues[0].description) >= 500_000


def test_parse_jira_xml_streaming_many_items(tmp_path):
    """Ensure iterparse path handles thousands of items without DOM bloat."""
    parts = ['<?xml version="1.0"?><rss version="0.92"><channel>']
    count = 2000
    for i in range(count):
        parts.append(
            f"<item><key>PROJ-{i}</key><summary>Item {i}</summary>"
            f"<type>Task</type><status>Open</status>"
            f"<assignee>user{i % 10}</assignee></item>"
        )
    parts.append("</channel></rss>")
    f = tmp_path / "many.xml"
    f.write_text("".join(parts))
    issues, is_jira = parse_xml_file(f)
    assert is_jira is True
    assert len(issues) == count
    assert issues[0].key == "PROJ-0"
    assert issues[-1].key == f"PROJ-{count - 1}"


def test_parse_jira_xml_dedupes_linked_issues(tmp_path):
    """The previous parser double-counted linked issues via a fallback scan."""
    content = """<?xml version='1.0'?>
    <rss version='0.92'><channel><item>
      <key>PROJ-1</key><summary>a</summary><type>Task</type><status>Open</status>
      <issuelinks>
        <issuelinktype>
          <name>Blocks</name>
          <outwardlinks><issuelink><issuekey>PROJ-2</issuekey></issuelink></outwardlinks>
          <inwardlinks><issuelink><issuekey>PROJ-3</issuekey></issuelink></inwardlinks>
        </issuelinktype>
      </issuelinks>
    </item></channel></rss>"""
    f = tmp_path / "links.xml"
    f.write_text(content)
    issues, _ = parse_xml_file(f)
    assert len(issues) == 1
    assert issues[0].linked_issues == ["PROJ-2", "PROJ-3"]  # no duplicates


def test_parse_csv_semicolon_delimiter(tmp_path):
    """European locales often export CSV with `;` delimiter."""
    content = (
        "Issue key;Summary;Status;Issue Type;Assignee\n"
        "PROJ-1;Bug;Open;Bug;alice\n"
        "PROJ-2;Story;Done;Story;bob\n"
    )
    f = tmp_path / "semi.csv"
    f.write_text(content)
    _headers, issues, is_jira = parse_csv_file(f)
    assert is_jira is True
    assert len(issues) == 2
    assert issues[1].assignee == "bob"
