"""Tests for the mcp_server package: config discovery, middleware, registration."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_server.app import build_app
from mcp_server.config import resolve_workspace
from mcp_server.middleware.audit import get_stats, hash_args, log_call
from mcp_server.middleware.budget import _enforce, cont_get


# ---------------------------------------------------------------------------
# Workspace discovery
# ---------------------------------------------------------------------------


class TestWorkspaceDiscovery:
    def test_cli_arg_takes_priority(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JARVIS_WORKSPACE", "/tmp/should-be-ignored")
        result = resolve_workspace(tmp_path)
        assert result == tmp_path.resolve()

    def test_env_var_used_when_no_cli_arg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JARVIS_WORKSPACE", str(tmp_path))
        assert resolve_workspace() == tmp_path.resolve()

    def test_falls_back_to_default_when_nothing_set(self, monkeypatch, tmp_path):
        monkeypatch.delenv("JARVIS_WORKSPACE", raising=False)
        # Point CONFIG_FILE to a non-existent path
        with patch("mcp_server.config.CONFIG_FILE", tmp_path / "missing.toml"):
            result = resolve_workspace()
        assert result == (Path.home() / "Jarvis").resolve()

    def test_reads_toml_config_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JARVIS_WORKSPACE", raising=False)
        cfg = tmp_path / "config.toml"
        target = tmp_path / "my-jarvis"
        cfg.write_text(f'workspace = "{target}"\n')
        with patch("mcp_server.config.CONFIG_FILE", cfg):
            assert resolve_workspace() == target.resolve()


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestBudgetEnforcement:
    def test_under_budget_passes_through(self):
        result = {"results": [{"a": 1}, {"a": 2}]}
        assert _enforce(result, max_tokens=10000) == result

    def test_truncates_oversize_list_and_mints_token(self):
        big = {"results": [{"x": "y" * 200} for _ in range(50)]}
        out = _enforce(big, max_tokens=200)
        assert out["truncated"] is True
        assert "continuation_token" in out
        assert len(out["results"]) < 50

    def test_continuation_token_returns_remaining(self):
        big = {"results": [{"i": i} for i in range(20)]}
        out = _enforce(big, max_tokens=50)
        assert out.get("truncated")
        token = out["continuation_token"]
        cont = cont_get(token)
        assert cont is not None
        assert "results" in cont

    def test_continuation_token_single_use(self):
        big = {"results": [{"i": i} for i in range(20)]}
        out = _enforce(big, max_tokens=50)
        token = out["continuation_token"]
        cont_get(token)
        assert cont_get(token) is None

    def test_truncates_long_string_content(self):
        big = {"content": "x" * 10000}
        out = _enforce(big, max_tokens=100)
        assert out.get("truncated")
        assert len(out["content"]) <= 400


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


class TestAudit:
    def test_hash_args_is_deterministic(self):
        h1 = hash_args({"b": 2, "a": 1})
        h2 = hash_args({"a": 1, "b": 2})
        assert h1 == h2 and len(h1) == 16

    @pytest.mark.asyncio
    async def test_log_call_writes_entry(self, tmp_path):
        async with log_call(tmp_path, tool="t1", args={"x": 1}, client_id="c1") as entry:
            entry["output_tokens"] = 42

        log_file = tmp_path / "app" / "logs" / "mcp.jsonl"
        assert log_file.exists()
        line = log_file.read_text().strip().splitlines()[-1]
        rec = json.loads(line)
        assert rec["tool"] == "t1"
        assert rec["client"] == "c1"
        assert rec["output_tokens"] == 42
        assert "elapsed_ms" in rec

    @pytest.mark.asyncio
    async def test_log_call_records_errors(self, tmp_path):
        with pytest.raises(RuntimeError):
            async with log_call(tmp_path, tool="t2", args={}):
                raise RuntimeError("boom")

        log_file = tmp_path / "app" / "logs" / "mcp.jsonl"
        rec = json.loads(log_file.read_text().strip().splitlines()[-1])
        assert rec["error"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_get_stats_aggregates(self, tmp_path):
        for tool in ("a", "a", "b"):
            async with log_call(tmp_path, tool=tool, args={}):
                pass

        stats = get_stats(tmp_path)
        assert stats["calls_today"] >= 3
        assert stats["top_tool"] == "a"


# ---------------------------------------------------------------------------
# FastMCP registration
# ---------------------------------------------------------------------------


class TestRegistration:
    @pytest.mark.asyncio
    async def test_read_only_app_lists_22_tools_plus_continue(self, tmp_path):
        app = build_app(tmp_path, allow_writes=False)
        tools = await app.list_tools()
        names = {t.name for t in tools}
        assert "jarvis_search_memory" in names
        assert "jarvis_workspace_stats" in names
        assert "jarvis_continue" in names
        # Write tools must NOT be exposed
        assert "jarvis_save_preference" not in names
        assert "jarvis_append_note" not in names

    @pytest.mark.asyncio
    async def test_writes_app_exposes_write_tools(self, tmp_path):
        app = build_app(tmp_path, allow_writes=True)
        names = {t.name for t in await app.list_tools()}
        assert "jarvis_save_preference" in names
        assert "jarvis_append_note" in names
        assert "jarvis_summarize_and_save" in names

    @pytest.mark.asyncio
    async def test_all_tools_have_descriptions(self, tmp_path):
        app = build_app(tmp_path, allow_writes=True)
        for tool in await app.list_tools():
            assert tool.description, f"Tool {tool.name} missing description"
