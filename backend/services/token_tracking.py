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

# In-memory cache for today's running totals so check_budget() doesn't
# re-read the full JSONL file on every Claude call.
_today_cache: Dict = {
    "date": "",
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_estimate": 0.0,
    "request_count": 0,
    "loaded": False,
}


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
    context_tokens: int = 0,
    tool_calls: int = 0,
    tool_rounds: int = 0,
    provider: str = "anthropic",
    workspace_path: Optional[Path] = None,
) -> Dict:
    """Log a single usage entry."""
    # Model-aware pricing (per million tokens)
    _PRICING = {
        "claude-haiku-4-20250514": (0.80, 4.0),
        "claude-sonnet-4-20250514": (3.0, 15.0),
    }
    cost_in, cost_out = _PRICING.get(model, (3.0, 15.0))
    cost_per_input = cost_in / 1_000_000
    cost_per_output = cost_out / 1_000_000

    # Try to use LiteLLM's model cost for non-Anthropic providers
    if provider != "anthropic":
        try:
            import litellm
            cost_estimate = litellm.completion_cost(
                model=model,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
        except Exception:
            # Fallback to default pricing
            cost_estimate = input_tokens * cost_per_input + output_tokens * cost_per_output
    else:
        cost_estimate = input_tokens * cost_per_input + output_tokens * cost_per_output

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "context_tokens": context_tokens,
        "tool_calls": tool_calls,
        "tool_rounds": tool_rounds,
        "model": model,
        "provider": provider,
        "cost_estimate": round(cost_estimate, 6),
    }

    # Ensure cache is loaded from disk *before* appending, so the new entry
    # isn't double-counted (once from disk read, once from increment).
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _ensure_cache_loaded(today, workspace_path)

    filepath = _usage_file(workspace_path)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Increment running totals
    _today_cache["input_tokens"] += input_tokens
    _today_cache["output_tokens"] += output_tokens
    _today_cache["cost_estimate"] += cost_estimate
    _today_cache["request_count"] += 1

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


def _ensure_cache_loaded(today: str, workspace_path: Optional[Path] = None) -> None:
    """Load today's totals from disk into the cache on first access or date rollover."""
    if _today_cache["loaded"] and _today_cache["date"] == today:
        return
    # Date changed or first call — rebuild from disk
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
    _today_cache.update({
        "date": today,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_estimate": total_cost,
        "request_count": count,
        "loaded": True,
    })


def invalidate_usage_cache() -> None:
    """Reset the in-memory cache. Useful for testing or after manual edits."""
    _today_cache.update({
        "date": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_estimate": 0.0,
        "request_count": 0,
        "loaded": False,
    })


def get_usage_today(workspace_path: Optional[Path] = None) -> Dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _ensure_cache_loaded(today, workspace_path)
    return {
        "date": today,
        "input_tokens": _today_cache["input_tokens"],
        "output_tokens": _today_cache["output_tokens"],
        "total_tokens": _today_cache["input_tokens"] + _today_cache["output_tokens"],
        "cost_estimate": round(_today_cache["cost_estimate"], 6),
        "request_count": _today_cache["request_count"],
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


DEFAULT_DAILY_BUDGET = 100_000


def get_daily_budget(workspace_path: Optional[Path] = None) -> int:
    """Read the daily token budget from preferences. 0 = unlimited."""
    from services.preference_service import load_preferences
    prefs = load_preferences(workspace_path)
    try:
        return int(prefs.get("daily_token_budget", DEFAULT_DAILY_BUDGET))
    except (ValueError, TypeError):
        return DEFAULT_DAILY_BUDGET


def check_budget(daily_budget: Optional[int] = None, workspace_path: Optional[Path] = None) -> Dict:
    """Check if daily usage is within budget. Returns warning level."""
    if daily_budget is None:
        daily_budget = get_daily_budget(workspace_path)
    usage = get_usage_today(workspace_path)
    total = usage["total_tokens"]
    if daily_budget <= 0:
        return {"level": "ok", "percent": 0, "used": total, "budget": 0}
    pct = (total / daily_budget * 100)
    level = "ok"
    if pct >= 100:
        level = "exceeded"
    elif pct >= 80:
        level = "warning"
    return {"level": level, "percent": round(pct, 1), "used": total, "budget": daily_budget}
