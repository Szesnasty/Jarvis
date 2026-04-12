# Step 11 — URL Ingest Pipeline (YouTube + Web)

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 10 — Polish](step-10-polish.md) | **Next**: [Step 11b — URL Ingest Frontend](step-11b-url-ingest-frontend.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Users can feed Jarvis with URLs — YouTube videos and web articles. The system extracts content, converts to Markdown notes with rich frontmatter, indexes them in SQLite FTS, and connects them in the knowledge graph. Claude can also ingest URLs as a tool during conversation.

---

## Dependencies

```
youtube-transcript-api   # YT transcript extraction, no ffmpeg needed
trafilatura              # Web article text extraction
markdownify              # HTML → Markdown conversion
```

Add to `backend/requirements.txt`.

---

## Files to Create / Modify

### Backend
```
backend/
├── services/
│   ├── url_ingest.py          # NEW — URL detection, YT + web extraction
│   ├── ingest.py              # MODIFY — import url_ingest for shared helpers
│   └── tools.py               # MODIFY — add ingest_url tool definition + executor
├── routers/
│   └── memory.py              # MODIFY — add POST /api/memory/ingest-url
```

---

## Specification

### A. URL Type Detection

```python
import re
from urllib.parse import urlparse, parse_qs

_YT_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?.*v=|youtu\.be/)([\w-]{11})"),
    re.compile(r"youtube\.com/embed/([\w-]{11})"),
    re.compile(r"youtube\.com/shorts/([\w-]{11})"),
]

def detect_url_type(url: str) -> tuple[str, str | None]:
    """Returns (type, video_id_or_none). type: 'youtube' | 'webpage' | 'invalid'"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "invalid", None
    for pat in _YT_PATTERNS:
        m = pat.search(url)
        if m:
            return "youtube", m.group(1)
    return "webpage", None
```

**Security**: Only allow `http://` and `https://` schemes. Reject `file://`, `javascript:`, `data:`, etc.

---

### B. YouTube Transcript Extraction

```python
from youtube_transcript_api import YouTubeTranscriptApi

async def _ingest_youtube(video_id: str, url: str, folder: str, workspace_path) -> dict:
    """Extract YT transcript → Markdown note."""
    # 1. Fetch transcript (try: pl, en, any available)
    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    transcript = transcript_list.find_transcript(['pl', 'en']).fetch()
    # Fallback: transcript_list.find_generated_transcript(['pl', 'en'])

    # 2. Build text from segments
    text = "\n\n".join(segment['text'] for segment in transcript)

    # 3. Get video title from transcript metadata or use video_id
    title = f"YouTube: {video_id}"  # basic fallback

    # 4. Create frontmatter
    frontmatter = {
        "title": title,
        "type": "youtube",
        "source": url,
        "video_id": video_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "tags": ["youtube", "video", "transcript"],
    }

    # 5. Save to memory/{folder}/yt-{video_id}.md
    # 6. Index in SQLite + rebuild graph
    ...
```

**Rules**:
- If no transcript available → raise `IngestError("No transcript available for this video")`
- Prefer manual transcripts over auto-generated
- Language preference: `['pl', 'en']` then fallback to any available
- Max transcript length: truncate at 50,000 chars (safety)

---

### C. Web Page Extraction

```python
import trafilatura
from markdownify import markdownify as md

async def _ingest_webpage(url: str, folder: str, workspace_path) -> dict:
    """Extract web article → Markdown note."""
    # 1. Fetch + extract with trafilatura
    downloaded = trafilatura.fetch_url(url)
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

    # 2. Extract metadata
    metadata = trafilatura.extract_metadata(downloaded)

    # 3. Convert HTML → Markdown
    markdown_content = md(result, heading_style="ATX")

    # 4. Build frontmatter
    frontmatter = {
        "title": metadata.title or urlparse(url).netloc,
        "type": "article",
        "source": url,
        "author": metadata.author or "",
        "date": metadata.date or now_date(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "tags": ["article", "web"],
    }

    # 5. Save to memory/{folder}/{slug}.md
    # 6. Index in SQLite + rebuild graph
    ...
```

**Rules**:
- Timeout on fetch: 15 seconds max
- Max content length: truncate markdown at 100,000 chars
- Strip tracking params from URL before storing as source
- If extraction fails → return clear error, don't save empty note

---

### D. Main Entry Point

```python
async def ingest_url(
    url: str,
    folder: str = "knowledge",
    summarize: bool = False,
    api_key: str | None = None,
    workspace_path: Path | None = None,
) -> dict:
    """Ingest a URL into memory. Returns note metadata."""
    url = _sanitize_url(url)
    url_type, video_id = detect_url_type(url)

    if url_type == "invalid":
        raise IngestError(f"Invalid or unsupported URL: {url}")

    if url_type == "youtube":
        result = await _ingest_youtube(video_id, url, folder, workspace_path)
    else:
        result = await _ingest_webpage(url, folder, workspace_path)

    # Optional: AI summary
    if summarize and api_key:
        result = await _summarize_note(result["path"], api_key, workspace_path)

    return result
```

---

### E. API Endpoint

`POST /api/memory/ingest-url`

```python
class UrlIngestRequest(BaseModel):
    url: str
    folder: str = "knowledge"
    summarize: bool = False

# Response: { path, title, type, source, word_count, summary? }
```

**Validation**:
- `url` must start with `http://` or `https://`
- `folder` alphanumeric + hyphens only
- Rate limit consideration: no more than 1 ingest per 2 seconds (future)

---

### F. Claude Tool: `ingest_url`

Add to `TOOLS` list:

```python
{
    "name": "ingest_url",
    "description": "Save a YouTube video transcript or web article to memory. Use when the user shares a URL and wants to remember or analyze its content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to ingest (YouTube or web page)",
            },
            "folder": {
                "type": "string",
                "description": "Target folder in memory (default: knowledge)",
                "default": "knowledge",
            },
            "summarize": {
                "type": "boolean",
                "description": "Whether to generate an AI summary",
                "default": False,
            },
        },
        "required": ["url"],
    },
}
```

In `execute_tool`:
```python
if name == "ingest_url":
    from services.url_ingest import ingest_url
    result = await ingest_url(
        tool_input["url"],
        folder=tool_input.get("folder", "knowledge"),
        summarize=tool_input.get("summarize", False),
        api_key=api_key,  # need to pass through
        workspace_path=workspace_path,
    )
    if session_id:
        session_service.record_note_access(session_id, result["path"])
    return json.dumps(result)
```

---

### G. Tests

```
backend/tests/
├── test_url_ingest.py         # NEW — unit tests for URL ingest
```

Test cases:
1. `detect_url_type` — youtube.com, youtu.be, shorts, embed, regular URLs, invalid schemes
2. `_ingest_youtube` — mock `YouTubeTranscriptApi`, verify markdown + frontmatter
3. `_ingest_webpage` — mock `trafilatura`, verify markdown + frontmatter
4. `ingest_url` — integration with mocked extractors
5. URL validation — reject `file://`, `javascript:`, `data:`, empty
6. API endpoint — mock service, test request/response
7. Claude tool — verify tool definition + execution
8. Truncation — very long content gets capped
9. Duplicate URL handling — second ingest gets `-1` suffix
