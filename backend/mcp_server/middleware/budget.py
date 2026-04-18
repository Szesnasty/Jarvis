"""Output budget enforcement + continuation token cache.

Wraps a tool handler so that oversize results are truncated and a
`continuation_token` is minted; clients call the `jarvis_continue` tool
(registered separately) to retrieve the next page.
"""

from __future__ import annotations

import functools
import json
import secrets
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable

_CONT_MAX = 50
_CONT_TTL = 300  # seconds

_continuation_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _cont_put(payload: Any) -> str:
    token = secrets.token_urlsafe(16)
    now = time.monotonic()
    _continuation_cache[token] = (now, payload)
    expired = [k for k, (ts, _) in _continuation_cache.items() if now - ts > _CONT_TTL]
    for k in expired:
        _continuation_cache.pop(k, None)
    while len(_continuation_cache) > _CONT_MAX:
        _continuation_cache.popitem(last=False)
    return token


def cont_get(token: str) -> Any | None:
    """Public for the jarvis_continue tool."""
    entry = _continuation_cache.pop(token, None)
    if entry is None:
        return None
    ts, payload = entry
    if time.monotonic() - ts > _CONT_TTL:
        return None
    return payload


def _enforce(result: Any, max_tokens: int) -> Any:
    if not isinstance(result, dict):
        return result

    serialized = json.dumps(result, default=str)
    if _estimate_tokens(serialized) <= max_tokens:
        return result

    # Truncate list-style results first
    if isinstance(result.get("results"), list):
        items = result["results"]
        kept: list[Any] = []
        meta_cost = _estimate_tokens(json.dumps({k: v for k, v in result.items() if k != "results"}, default=str))
        running = meta_cost
        for item in items:
            cost = _estimate_tokens(json.dumps(item, default=str))
            if running + cost > max_tokens - 100:
                break
            kept.append(item)
            running += cost
        remaining = items[len(kept):]
        truncated = {**result, "results": kept, "truncated": True}
        if remaining:
            truncated["continuation_token"] = _cont_put({"results": remaining})
        return truncated

    # Truncate string-heavy results
    if isinstance(result.get("content"), str):
        char_budget = max_tokens * 4
        content = result["content"]
        if len(content) > char_budget:
            return {
                **result,
                "content": content[:char_budget],
                "truncated": True,
                "continuation_token": _cont_put({"content": content[char_budget:]}),
            }

    return result


def enforce_budget(max_tokens: int):
    """Decorator: trim oversize tool results to `max_tokens` and emit continuation."""

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(**kwargs: Any) -> Any:
            result = await fn(**kwargs)
            return _enforce(result, max_tokens)

        return wrapper

    return decorator
