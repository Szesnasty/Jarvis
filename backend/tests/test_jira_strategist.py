"""Tests for step 22g — Jira Strategist specialist + tools + duel presets."""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_workspace(tmp_path: Path) -> Path:
    """Create minimal workspace with Jira tables."""
    ws = tmp_path / "workspace"
    (ws / "app").mkdir(parents=True)
    (ws / "memory" / "jira" / "AUTH").mkdir(parents=True)
    (ws / "memory" / "decisions").mkdir(parents=True)
    (ws / "agents").mkdir(parents=True)

    db_path = ws / "app" / "jarvis.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS issues (
            issue_key TEXT PRIMARY KEY,
            project_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            issue_type TEXT NOT NULL,
            status TEXT NOT NULL,
            status_category TEXT,
            priority TEXT,
            assignee TEXT,
            reporter TEXT,
            epic_key TEXT,
            parent_key TEXT,
            due_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source_url TEXT,
            note_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS issue_labels (
            issue_key TEXT NOT NULL,
            label TEXT NOT NULL,
            PRIMARY KEY (issue_key, label)
        );
        CREATE TABLE IF NOT EXISTS issue_components (
            issue_key TEXT NOT NULL,
            component TEXT NOT NULL,
            PRIMARY KEY (issue_key, component)
        );
        CREATE TABLE IF NOT EXISTS issue_sprints (
            issue_key TEXT NOT NULL,
            sprint_name TEXT NOT NULL,
            sprint_state TEXT,
            PRIMARY KEY (issue_key, sprint_name)
        );
        CREATE TABLE IF NOT EXISTS issue_links (
            source_key TEXT NOT NULL,
            target_key TEXT NOT NULL,
            link_type TEXT NOT NULL,
            direction TEXT NOT NULL,
            PRIMARY KEY (source_key, target_key, link_type, direction)
        );
        CREATE TABLE IF NOT EXISTS enrichments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt_version INTEGER NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            raw_output TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            duration_ms INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(subject_type, subject_id, content_hash, model_id, prompt_version)
        );
        CREATE VIEW IF NOT EXISTS latest_enrichment AS
        SELECT e.*
        FROM enrichments e
        JOIN (
            SELECT subject_type, subject_id, MAX(created_at) AS mx
            FROM enrichments WHERE status='ok'
            GROUP BY subject_type, subject_id
        ) l ON e.subject_type = l.subject_type
          AND e.subject_id = l.subject_id
          AND e.created_at = l.mx;
    """)

    # Seed test data
    conn.execute("""
        INSERT INTO issues VALUES
        ('AUTH-155','AUTH','Add 2FA support','desc','Task','In Progress',
         'in-progress','High','Alice','Bob','AUTH-100',NULL,NULL,
         '2026-01-01','2026-04-10',NULL,'memory/jira/AUTH/AUTH-155.md','h1','2026-04-01')
    """)
    conn.execute("""
        INSERT INTO issues VALUES
        ('AUTH-120','AUTH','Security audit','desc','Task','To Do',
         'to-do','Medium','Charlie','Bob',NULL,NULL,NULL,
         '2026-01-01','2026-04-08',NULL,'memory/jira/AUTH/AUTH-120.md','h2','2026-04-01')
    """)
    conn.execute("""
        INSERT INTO issues VALUES
        ('AUTH-142','AUTH','Rate limiter refactor','desc','Bug','Done',
         'done','Low','Alice','Bob',NULL,NULL,NULL,
         '2026-01-01','2026-04-05',NULL,'memory/jira/AUTH/AUTH-142.md','h3','2026-04-01')
    """)

    # Sprints
    conn.execute("INSERT INTO issue_sprints VALUES ('AUTH-155','Sprint 10','ACTIVE')")
    conn.execute("INSERT INTO issue_sprints VALUES ('AUTH-120','Sprint 10','ACTIVE')")
    conn.execute("INSERT INTO issue_sprints VALUES ('AUTH-142','Sprint 9','CLOSED')")

    # Links: AUTH-155 is blocked by AUTH-120
    conn.execute("""
        INSERT INTO issue_links VALUES
        ('AUTH-155','AUTH-120','is blocked by','outbound')
    """)
    conn.execute("""
        INSERT INTO issue_links VALUES
        ('AUTH-120','AUTH-155','blocks','outbound')
    """)

    # Enrichment for AUTH-155
    payload = json.dumps({
        "summary": "Add two-factor authentication",
        "risk_level": "high",
        "ambiguity_level": "partial",
        "business_area": "auth",
        "work_type": "feature",
        "execution_type": "implementation",
        "actionable_next_step": "Define 2FA provider",
        "hidden_concerns": ["migration complexity"],
        "keywords": ["2fa", "auth", "security"],
        "likely_related_issue_keys": [],
        "likely_related_note_paths": [],
    })
    conn.execute("""
        INSERT INTO enrichments
        (subject_type, subject_id, content_hash, model_id, prompt_version,
         status, payload, created_at)
        VALUES ('jira_issue','AUTH-155','h1','ollama:qwen',1,'ok',?,
                '2026-04-10T00:00:00')
    """, (payload,))

    conn.commit()
    conn.close()
    return ws


def _settings_mock(ws: Path):
    """Return a mock settings object pointing at the workspace."""
    mock = MagicMock()
    mock.workspace_path = ws
    return mock


# ── Test: tool definitions ────────────────────────────────────────────────────


class TestToolDefinitions:
    def test_jira_tools_registered(self):
        from services.tools import TOOLS
        jira_names = [t["name"] for t in TOOLS if t["name"].startswith("jira_")]
        assert set(jira_names) == {
            "jira_list_issues",
            "jira_describe_issue",
            "jira_blockers_of",
            "jira_depends_on",
            "jira_sprint_risk",
            "jira_cluster_by_topic",
        }

    def test_tools_have_valid_schemas(self):
        from services.tools import TOOLS
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            schema = tool["input_schema"]
            assert schema["type"] == "object"
            assert "properties" in schema

    def test_total_tool_count(self):
        from services.tools import TOOLS
        assert len(TOOLS) >= 17  # 11 core + 6 jira


# ── Test: jira_list_issues ────────────────────────────────────────────────────


class TestJiraListIssues:
    @pytest.fixture
    def ws(self, tmp_path):
        return _make_workspace(tmp_path)

    @pytest.mark.asyncio
    async def test_list_all(self, ws):
        from services.tools.jira_tools import jira_list_issues
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_list_issues({}, ws)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_filter_by_status(self, ws):
        from services.tools.jira_tools import jira_list_issues
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_list_issues({"status": "in-progress"}, ws)
        assert len(result) == 1
        assert result[0]["key"] == "AUTH-155"

    @pytest.mark.asyncio
    async def test_filter_by_sprint_state(self, ws):
        from services.tools.jira_tools import jira_list_issues
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_list_issues({"sprint_state": "ACTIVE"}, ws)
        keys = {r["key"] for r in result}
        assert keys == {"AUTH-155", "AUTH-120"}

    @pytest.mark.asyncio
    async def test_enrichment_attached(self, ws):
        from services.tools.jira_tools import jira_list_issues
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_list_issues({}, ws)
        enriched = [r for r in result if r.get("risk")]
        assert len(enriched) >= 1
        assert enriched[0]["risk"] == "high"

    @pytest.mark.asyncio
    async def test_limit_respected(self, ws):
        from services.tools.jira_tools import jira_list_issues
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_list_issues({"limit": 1}, ws)
        assert len(result) == 1


# ── Test: jira_describe_issue ─────────────────────────────────────────────────


class TestJiraDescribeIssue:
    @pytest.fixture
    def ws(self, tmp_path):
        return _make_workspace(tmp_path)

    @pytest.mark.asyncio
    async def test_found(self, ws):
        from services.tools.jira_tools import jira_describe_issue
        with patch("services.tools.jira_tools._jira_db") as mock_db, \
             patch("services.tools.jira_tools.graph_service") as mock_gs:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            mock_gs.load_graph.return_value = None
            result = await jira_describe_issue({"key": "AUTH-155"}, ws)
        assert result["key"] == "AUTH-155"
        assert result["assignee"] == "Alice"
        assert "enrichment" in result
        assert result["enrichment"]["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_not_found(self, ws):
        from services.tools.jira_tools import jira_describe_issue
        with patch("services.tools.jira_tools._jira_db") as mock_db, \
             patch("services.tools.jira_tools.graph_service") as mock_gs:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            mock_gs.load_graph.return_value = None
            result = await jira_describe_issue({"key": "NOPE-999"}, ws)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_hard_links(self, ws):
        from services.tools.jira_tools import jira_describe_issue
        with patch("services.tools.jira_tools._jira_db") as mock_db, \
             patch("services.tools.jira_tools.graph_service") as mock_gs:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            mock_gs.load_graph.return_value = None
            result = await jira_describe_issue({"key": "AUTH-155"}, ws)
        assert "is blocked by" in result["hard_links"]
        assert "AUTH-120" in result["hard_links"]["is blocked by"]


# ── Test: jira_blockers_of ────────────────────────────────────────────────────


class TestJiraBlockersOf:
    @pytest.fixture
    def ws(self, tmp_path):
        return _make_workspace(tmp_path)

    def test_direct_blocker(self, ws):
        from services.tools.jira_tools import jira_blockers_of
        with patch("services.tools.jira_tools._jira_db") as mock_db, \
             patch("services.tools.jira_tools.graph_service") as mock_gs:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            mock_gs.load_graph.return_value = None
            result = jira_blockers_of({"key": "AUTH-155"}, ws)
        assert "AUTH-120" in result["direct_blockers"]

    def test_bfs_depth_cap(self, ws):
        """BFS respects max_depth=3."""
        from services.tools.jira_tools import _bfs_links
        conn = sqlite3.connect(str(ws / "app" / "jarvis.db"))
        conn.row_factory = sqlite3.Row
        direct, transitive = _bfs_links(
            conn, "AUTH-155", "is blocked by", "outbound", max_depth=3,
        )
        conn.close()
        # Only AUTH-120 blocks AUTH-155 directly; no transitive chain
        assert direct == ["AUTH-120"]
        assert transitive == []


# ── Test: jira_depends_on ─────────────────────────────────────────────────────


class TestJiraDependsOn:
    @pytest.fixture
    def ws(self, tmp_path):
        return _make_workspace(tmp_path)

    def test_direct_dependent(self, ws):
        from services.tools.jira_tools import jira_depends_on
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = jira_depends_on({"key": "AUTH-120"}, ws)
        assert "AUTH-155" in result["direct_dependents"]


# ── Test: jira_sprint_risk ────────────────────────────────────────────────────


class TestJiraSprintRisk:
    @pytest.fixture
    def ws(self, tmp_path):
        return _make_workspace(tmp_path)

    @pytest.mark.asyncio
    async def test_active_sprint_default(self, ws):
        from services.tools.jira_tools import jira_sprint_risk
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_sprint_risk({}, ws)
        assert result["sprint_name"] == "Sprint 10"
        assert len(result["issues"]) == 2
        assert "AUTH-155" in result["top_risks"]

    @pytest.mark.asyncio
    async def test_bottlenecks(self, ws):
        from services.tools.jira_tools import jira_sprint_risk
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_sprint_risk({}, ws)
        assignees = [b["assignee"] for b in result["bottlenecks"]]
        assert "Alice" in assignees or "Charlie" in assignees


# ── Test: jira_cluster_by_topic ───────────────────────────────────────────────


class TestJiraClusterByTopic:
    @pytest.fixture
    def ws(self, tmp_path):
        return _make_workspace(tmp_path)

    @pytest.mark.asyncio
    async def test_cluster_all(self, ws):
        from services.tools.jira_tools import jira_cluster_by_topic
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_cluster_by_topic({}, ws)
        # AUTH-155 has enrichment with area="auth", others "uncategorized"
        areas = {c["business_area"] for c in result}
        assert "auth" in areas

    @pytest.mark.asyncio
    async def test_cluster_root_keys(self, ws):
        from services.tools.jira_tools import jira_cluster_by_topic
        with patch("services.tools.jira_tools._jira_db") as mock_db:
            mock_db.return_value = sqlite3.connect(str(ws / "app" / "jarvis.db"))
            mock_db.return_value.row_factory = sqlite3.Row
            result = await jira_cluster_by_topic(
                {"root_keys": ["AUTH-155"]}, ws
            )
        all_keys = []
        for c in result:
            all_keys.extend(c["issue_keys"])
        assert "AUTH-155" in all_keys
        assert "AUTH-120" not in all_keys


# ── Test: specialist profile ──────────────────────────────────────────────────


class TestJiraStrategistProfile:
    def test_builtin_has_jira_tools(self):
        from services.specialist_service import _BUILTIN_SPECIALISTS
        js = next(s for s in _BUILTIN_SPECIALISTS if s["id"] == "jira-strategist")
        assert "jira_list_issues" in js["tools"]
        assert "jira_describe_issue" in js["tools"]
        assert "jira_blockers_of" in js["tools"]
        assert "jira_sprint_risk" in js["tools"]

    def test_seed_creates_file(self, tmp_path):
        ws = tmp_path / "ws"
        (ws / "agents").mkdir(parents=True)
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.specialist_service import seed_builtin_specialists
            created = seed_builtin_specialists(ws)
        assert "jira-strategist" in created
        fp = ws / "agents" / "jira-strategist.json"
        assert fp.exists()
        data = json.loads(fp.read_text())
        assert "jira_list_issues" in data["tools"]

    def test_seed_idempotent(self, tmp_path):
        ws = tmp_path / "ws"
        (ws / "agents").mkdir(parents=True)
        with patch("services.specialist_service.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.specialist_service import seed_builtin_specialists
            seed_builtin_specialists(ws)
            created2 = seed_builtin_specialists(ws)
        assert created2 == []  # Nothing re-created

    def test_specialist_scope_folders(self):
        from services.specialist_service import _BUILTIN_SPECIALISTS
        js = next(s for s in _BUILTIN_SPECIALISTS if s["id"] == "jira-strategist")
        assert "memory/jira/**" in js["sources"]
        assert "memory/people/**" in js["sources"]


# ── Test: duel presets ────────────────────────────────────────────────────────


class TestDuelPresets:
    def test_seed_creates_files(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        with patch("services.duel_presets.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.duel_presets import seed_builtin_presets
            created = seed_builtin_presets(ws)
        assert len(created) == 4
        assert "delivery-vs-risk" in created

    def test_list_presets(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        with patch("services.duel_presets.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.duel_presets import seed_builtin_presets, list_presets
            seed_builtin_presets(ws)
            presets = list_presets(ws)
        assert len(presets) == 4
        ids = {p["id"] for p in presets}
        assert "product-vs-tech" in ids

    def test_get_preset(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        with patch("services.duel_presets.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.duel_presets import seed_builtin_presets, get_preset
            seed_builtin_presets(ws)
            preset = get_preset("pragmatist-vs-refactorer", ws)
        assert preset is not None
        assert preset["side_a"]["stance"] == "get it done"

    def test_get_missing_preset(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        with patch("services.duel_presets.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.duel_presets import get_preset
            assert get_preset("nonexistent", ws) is None

    def test_seed_idempotent(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        with patch("services.duel_presets.get_settings") as m:
            m.return_value = _settings_mock(ws)
            from services.duel_presets import seed_builtin_presets
            seed_builtin_presets(ws)
            created2 = seed_builtin_presets(ws)
        assert created2 == []


# ── Test: duel verdict → graph edges ──────────────────────────────────────────


class TestDuelVerdictEdges:
    def test_issue_keys_extracted_from_text(self):
        """Verify regex extraction of issue keys from duel text."""
        import re
        text = "Consider AUTH-155 and AUTH-120 as blockers. Also FOO-42."
        keys = set(re.findall(r"\b([A-Z][A-Z0-9]+-\d+)\b", text))
        assert keys == {"AUTH-155", "AUTH-120", "FOO-42"}

    def test_vote_margin_calculation(self):
        """vote_margin = abs(a - b) / max(a + b, 1)."""
        total_a, total_b = 18, 12
        margin = abs(total_a - total_b) / max(total_a + total_b, 1)
        assert 0.19 < margin < 0.21
        weight = round(min(margin + 0.5, 1.0), 2)
        assert weight == 0.7
