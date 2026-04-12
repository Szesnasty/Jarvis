import json

import pytest

from services.token_tracking import (
    check_budget,
    get_usage_by_day,
    get_usage_summary,
    get_usage_today,
    log_usage,
)

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "app" / "logs").mkdir(parents=True)
    return tmp_path


def test_log_usage_creates_entry(ws):
    entry = log_usage(100, 50, workspace_path=ws)
    assert "timestamp" in entry
    filepath = ws / "app" / "logs" / "token_usage.jsonl"
    assert filepath.exists()
    lines = filepath.read_text().strip().split("\n")
    assert len(lines) == 1


def test_log_usage_fields(ws):
    entry = log_usage(1000, 500, workspace_path=ws)
    assert entry["input_tokens"] == 1000
    assert entry["output_tokens"] == 500
    assert entry["total_tokens"] == 1500
    assert entry["model"] == "claude-sonnet-4-20250514"
    assert entry["cost_estimate"] > 0


def test_get_usage_today(ws):
    log_usage(100, 50, workspace_path=ws)
    log_usage(200, 100, workspace_path=ws)
    today = get_usage_today(workspace_path=ws)
    assert today["input_tokens"] == 300
    assert today["output_tokens"] == 150
    assert today["request_count"] == 2


def test_get_usage_by_day(ws):
    log_usage(100, 50, workspace_path=ws)
    result = get_usage_by_day(workspace_path=ws)
    assert len(result) == 1
    assert result[0]["request_count"] == 1


def test_get_usage_empty(ws):
    summary = get_usage_summary(workspace_path=ws)
    assert summary["total"] == 0


def test_budget_warning_at_80pct(ws):
    # Budget of 1000, use 850 tokens
    log_usage(600, 250, workspace_path=ws)
    result = check_budget(daily_budget=1000, workspace_path=ws)
    assert result["level"] == "warning"
    assert result["percent"] >= 80


def test_budget_warning_at_100pct(ws):
    log_usage(800, 300, workspace_path=ws)
    result = check_budget(daily_budget=1000, workspace_path=ws)
    assert result["level"] == "exceeded"
    assert result["percent"] >= 100


def test_budget_configurable(ws):
    log_usage(100, 50, workspace_path=ws)
    result = check_budget(daily_budget=500, workspace_path=ws)
    assert result["budget"] == 500
    assert "level" in result


def test_usage_log_survives_restart(ws):
    log_usage(100, 50, workspace_path=ws)
    # Simulate "restart" by reading from disk
    summary = get_usage_summary(workspace_path=ws)
    assert summary["total"] == 150


def test_usage_api_endpoint(ws):
    """Test that usage summary returns correct structure."""
    log_usage(100, 50, workspace_path=ws)
    summary = get_usage_summary(workspace_path=ws)
    assert "total" in summary
    assert "input_tokens" in summary
    assert "output_tokens" in summary
    assert "cost_estimate" in summary
    assert "request_count" in summary
