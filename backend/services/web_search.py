import logging
from typing import Any

from services.privacy import web_search_enabled, is_offline_mode

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


async def web_search(query: str, max_results: int = MAX_RESULTS) -> list[dict[str, Any]]:
    """Search the web using DuckDuckGo. Returns list of {title, url, snippet}."""
    if not web_search_enabled():
        reason = (
            "Web search is blocked because Offline Mode is enabled."
            if is_offline_mode()
            else "Web search is disabled in Settings → Privacy."
        )
        logger.info("web_search blocked by privacy settings: %s", reason)
        return [{"error": reason}]

    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search package not installed")
        return [{"error": "Web search unavailable — duckduckgo-search not installed"}]

    max_results = min(max_results, 10)

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return [{"error": f"Web search failed: {exc}"}]

    results = []
    for item in raw:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", ""),
        })

    return results
