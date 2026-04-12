import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from config import get_settings
from services.ingest import IngestError

logger = logging.getLogger(__name__)

MAX_TRANSCRIPT_CHARS = 50_000
MAX_WEBPAGE_CHARS = 100_000

_YT_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?.*v=|youtu\.be/)([\w-]{11})"),
    re.compile(r"youtube\.com/embed/([\w-]{11})"),
    re.compile(r"youtube\.com/shorts/([\w-]{11})"),
]

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid",
}


def detect_url_type(url: str) -> tuple:
    """Returns (type, video_id_or_none). type: 'youtube' | 'webpage' | 'invalid'"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "invalid", None
    for pat in _YT_PATTERNS:
        m = pat.search(url)
        if m:
            return "youtube", m.group(1)
    return "webpage", None


def _sanitize_url(url: str) -> str:
    """Strip tracking params and normalize."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise IngestError(f"Invalid URL scheme: {parsed.scheme}")
    # Strip tracking params
    qs = parse_qs(parsed.query, keep_blank_values=False)
    cleaned = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
    new_query = urlencode(cleaned, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _memory_dir(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    i = 1
    while True:
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _build_frontmatter(meta: dict) -> str:
    fm = "---\n"
    for k, v in meta.items():
        if isinstance(v, list):
            fm += f"{k}: {json.dumps(v)}\n"
        else:
            fm += f"{k}: {v}\n"
    fm += "---\n\n"
    return fm


async def _ingest_youtube(
    video_id: str,
    url: str,
    folder: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    from youtube_transcript_api import YouTubeTranscriptApi

    ytt = YouTubeTranscriptApi()

    # Try fetching transcript: pl first, then en, then any available
    try:
        transcript = ytt.fetch(video_id, languages=["pl", "en"])
    except Exception:
        try:
            transcript = ytt.fetch(video_id)
        except Exception as exc:
            raise IngestError(f"No transcript available for video {video_id}: {exc}")

    # Build text from snippets
    segments = [snippet.text for snippet in transcript]
    text = "\n\n".join(segments)
    if len(text) > MAX_TRANSCRIPT_CHARS:
        text = text[:MAX_TRANSCRIPT_CHARS] + "\n\n[...transcript truncated]"

    title = f"YouTube: {video_id}"

    frontmatter = {
        "title": title,
        "type": "youtube",
        "source": url,
        "video_id": video_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "tags": ["youtube", "video", "transcript"],
    }

    mem = _memory_dir(workspace_path)
    folder_path = mem / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    filename = f"yt-{video_id}.md"
    target = _unique_path(folder_path / filename)
    content = _build_frontmatter(frontmatter) + f"# {title}\n\n{text}\n"
    target.write_text(content, encoding="utf-8")

    rel_path = target.relative_to(mem).as_posix()

    # Index in SQLite
    from services.memory_service import index_note_file
    try:
        await index_note_file(rel_path, workspace_path=workspace_path)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise IngestError(f"Failed to index note: {exc}") from exc

    # Rebuild graph
    try:
        from services.graph_service import rebuild_graph
        rebuild_graph(workspace_path=workspace_path)
    except Exception as exc:
        logger.warning("Graph rebuild after YT ingest failed: %s", exc)

    word_count = len(text.split())
    return {
        "path": rel_path,
        "title": title,
        "type": "youtube",
        "source": url,
        "word_count": word_count,
    }


async def _ingest_webpage(
    url: str,
    folder: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    import trafilatura
    from markdownify import markdownify as md
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    downloaded = None
    try:
        response = requests.get(url, headers=headers, timeout=15, verify=True)
        response.raise_for_status()
        downloaded = response.text
    except Exception as exc:
        # Retry without SSL verification if cert is bad
        try:
            logger.warning(f"First attempt failed for {url}, retrying without SSL verification: {exc}")
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            downloaded = response.text
        except Exception as exc2:
            raise IngestError(f"Could not fetch URL: {url} ({exc2})")

    if not downloaded:
        raise IngestError(f"Could not fetch URL: {url}")

    result = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        output_format="html",
    )
    if not result:
        raise IngestError(f"Could not extract content from: {url}")

    metadata = trafilatura.extract_metadata(downloaded)

    markdown_content = md(result, heading_style="ATX")
    if len(markdown_content) > MAX_WEBPAGE_CHARS:
        markdown_content = markdown_content[:MAX_WEBPAGE_CHARS] + "\n\n[...content truncated]"

    title = (metadata.title if metadata and metadata.title else urlparse(url).netloc) or "Untitled"
    author = (metadata.author if metadata and metadata.author else "") or ""
    date = (metadata.date if metadata and metadata.date else _now_date()) or _now_date()

    frontmatter = {
        "title": title,
        "type": "article",
        "source": url,
        "author": author,
        "date": date,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "tags": ["article", "web"],
    }

    mem = _memory_dir(workspace_path)
    folder_path = mem / folder
    folder_path.mkdir(parents=True, exist_ok=True)

    slug = _slugify(title) or "article"
    filename = f"{slug}.md"
    target = _unique_path(folder_path / filename)
    content = _build_frontmatter(frontmatter) + f"# {title}\n\n{markdown_content}\n"
    target.write_text(content, encoding="utf-8")

    rel_path = target.relative_to(mem).as_posix()

    # Index in SQLite
    from services.memory_service import index_note_file
    try:
        await index_note_file(rel_path, workspace_path=workspace_path)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise IngestError(f"Failed to index note: {exc}") from exc

    # Rebuild graph
    try:
        from services.graph_service import rebuild_graph
        rebuild_graph(workspace_path=workspace_path)
    except Exception as exc:
        logger.warning("Graph rebuild after web ingest failed: %s", exc)

    word_count = len(markdown_content.split())
    return {
        "path": rel_path,
        "title": title,
        "type": "article",
        "source": url,
        "word_count": word_count,
    }


async def ingest_url(
    url: str,
    folder: str = "knowledge",
    summarize: bool = False,
    api_key: Optional[str] = None,
    workspace_path: Optional[Path] = None,
) -> Dict:
    """Ingest a URL into memory. Returns note metadata."""
    url = _sanitize_url(url)
    url_type, video_id = detect_url_type(url)

    if url_type == "invalid":
        raise IngestError(f"Invalid or unsupported URL: {url}")

    if url_type == "youtube":
        result = await _ingest_youtube(video_id, url, folder, workspace_path)
    else:
        result = await _ingest_webpage(url, folder, workspace_path)

    if summarize and api_key:
        from services.ingest import smart_enrich
        try:
            enrich = await smart_enrich(result["path"], api_key, workspace_path)
            result["summary"] = enrich.get("summary", "")
        except Exception as exc:
            logger.warning("AI summary failed: %s", exc)

    return result
