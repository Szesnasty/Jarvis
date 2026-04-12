import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)

TOTAL_BUDGET = 4000
CONTEXT_BUDGET = 2500
PREFERENCES_BUDGET = 500
SPECIALIST_BUDGET = 500
HISTORY_BUDGET = 500


def _logs_dir(workspace_path: Optional[Path] = None) -> Path:
    d = (workspace_path or get_settings().workspace_path) / "app" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _usage_file(workspace_path: Optional[Path] = None) -> Path:
    return _logs_dir(workspace_path) / "token_usage.jsonl"


def log_usage(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-sonnet-4-20250514",
    workspace_path: Optional[Path] = None,
) -> Dict:
    """Log a single usage entry."""
    cost_per_input = 3.0 / 1_000_000   # $3/MTok input
    cost_per_output = 15.0 / 1_000_000  # $15/MTok output
    cost_estimate = input_tokens * cost_per_input + output_tokens * cost_per_output

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "model": model,
        "cost_estimate": round(cost_estimate, 6),
    }
    filepath = _usage_file(workspace_path)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def _read_entries(workspace_path: Optional[Path] = None) -> List[Dict]:
    filepath = _usage_file(workspace_path)
    if not filepath.exists():
        return []
    entries = []
    for line in filepath.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def get_usage_today(workspace_path: Optional[Path] = None) -> Dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = _read_entries(workspace_path)
    total_input = 0
    total_output = 0
    total_cost = 0.0
    count = 0
    for e in entries:
        if e.get("timestamp", "").startswith(today):
            total_input += e.get("input_tokens", 0)
            total_output += e.get("output_tokens", 0)
            total_cost += e.get("cost_estimate", 0)
            count += 1
    return {
        "date": today,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "cost_estimate": round(total_cost, 6),
        "request_count": count,
    }


def get_usage_by_day(workspace_path: Optional[Path] = None) -> List[Dict]:
    entries = _read_entries(workspace_path)
    days: Dict[str, Dict] = {}
    for e in entries:
        day = e.get("timestamp", "")[:10]
        if day not in days:
            days[day] = {"date": day, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_estimate": 0.0, "request_count": 0}
        days[day]["input_tokens"] += e.get("input_tokens", 0)
        days[day]["output_tokens"] += e.get("output_tokens", 0)
        days[day]["total_tokens"] += e.get("input_tokens", 0) + e.get("output_tokens", 0)
        days[day]["cost_estimate"] += e.get("cost_estimate", 0)
        days[day]["request_count"] += 1
    result = sorted(days.values(), key=lambda d: d["date"], reverse=True)
    for r in result:
        r["cost_estimate"] = round(r["cost_estimate"], 6)
    return result


def get_usage_summary(workspace_path: Optional[Path] = None) -> Dict:
    entries = _read_entries(workspace_path)
    if not entries:
        return {"total": 0, "input_tokens": 0, "output_tokens": 0, "cost_estimate": 0.0}
    total_input = sum(e.get("input_tokens", 0) for e in entries)
    total_output = sum(e.get("output_tokens", 0) for e in entries)
    total_cost = sum(e.get("cost_estimate", 0) for e in entries)
    return {
        "total": total_input + total_output,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_estimate": round(total_cost, 6),
        "request_count": len(entries),
    }


def check_budget(daily_budget: int = 100000, workspace_path: Optional[Path] = None) -> Dict:
    """Check if daily usage is within budget. Returns warning level."""
    usage = get_usage_today(workspace_path)
    total = usage["total_tokens"]
    pct = (total / daily_budget * 100) if daily_budget > 0 else 0
    level = "ok"
    if pct >= 100:
        level = "exceeded"
    elif pct >= 80:
        level = "warning"
    return {"level": level, "percent": round(pct, 1), "used": total, "budget": daily_budget}
