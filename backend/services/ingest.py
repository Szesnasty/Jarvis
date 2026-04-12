import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


class IngestError(Exception):
    pass


def _memory_dir(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _unique_path(target: Path) -> Path:
    """If target exists, add numeric suffix."""
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


def _make_frontmatter(title: str, source: str, tags: Optional[list] = None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tag_str = json.dumps(tags or ["imported"])
    return f"---\ntitle: {title}\ndate: {now}\nsource: {source}\ntags: {tag_str}\n---\n\n"


def _extract_pdf_text(file_path: Path) -> str:
    """Extract text from PDF using pdfplumber if available, else fallback."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        raise IngestError("pdfplumber not installed. Install with: pip install pdfplumber")


async def fast_ingest(
    file_path: Path,
    target_folder: str = "knowledge",
    workspace_path: Optional[Path] = None,
) -> Dict:
    """Import a file into memory without AI."""
    if not file_path.exists():
        raise IngestError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IngestError(f"Unsupported file type: {ext}")

    title = file_path.stem
    mem = _memory_dir(workspace_path)
    folder = mem / target_folder
    folder.mkdir(parents=True, exist_ok=True)

    if ext == ".md":
        content = file_path.read_text(encoding="utf-8")
        # Check if it already has frontmatter
        if not content.strip().startswith("---"):
            content = _make_frontmatter(title, str(file_path)) + content
        target = _unique_path(folder / file_path.name)
        target.write_text(content, encoding="utf-8")

    elif ext == ".txt":
        content = file_path.read_text(encoding="utf-8")
        md_name = f"{_slugify(title)}.md"
        fm = _make_frontmatter(title, str(file_path))
        target = _unique_path(folder / md_name)
        target.write_text(fm + content, encoding="utf-8")

    elif ext == ".pdf":
        text = _extract_pdf_text(file_path)
        md_name = f"{_slugify(title)}.md"
        fm = _make_frontmatter(title, str(file_path))
        target = _unique_path(folder / md_name)
        target.write_text(fm + text, encoding="utf-8")

    else:
        raise IngestError(f"Unsupported: {ext}")

    # Update index
    try:
        from services.memory_service import reindex_all
        await reindex_all(workspace_path=workspace_path)
    except Exception as exc:
        logger.warning("Reindex after ingest failed: %s", exc)

    rel_path = str(target.relative_to(mem))
    return {
        "path": rel_path,
        "title": title,
        "folder": target_folder,
        "source": str(file_path),
        "size": target.stat().st_size,
    }


async def smart_enrich(
    note_path: str,
    api_key: str,
    workspace_path: Optional[Path] = None,
) -> Dict:
    """Use Claude to enhance a note with summary and tags."""
    from services._anthropic_client import create_client

    mem = _memory_dir(workspace_path)
    full_path = mem / note_path
    if not full_path.exists():
        raise IngestError(f"Note not found: {note_path}")

    content = full_path.read_text(encoding="utf-8")
    truncated = content[:3000]

    client = create_client(api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Analyze this note and return JSON with: summary (1-2 sentences), tags (list of 3-5 keywords).\n\nNote:\n{truncated}\n\nReturn only valid JSON.",
        }],
    )

    text = response.content[0].text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"summary": text[:200], "tags": []}

    # Update frontmatter
    from utils.markdown import parse_frontmatter
    fm, body = parse_frontmatter(content)
    fm["summary"] = data.get("summary", "")
    existing_tags = fm.get("tags", [])
    new_tags = data.get("tags", [])
    fm["tags"] = list(set(existing_tags + new_tags))

    # Rebuild file
    fm_str = "---\n"
    for k, v in fm.items():
        if isinstance(v, list):
            fm_str += f"{k}: {json.dumps(v)}\n"
        else:
            fm_str += f"{k}: {v}\n"
    fm_str += "---\n\n"
    full_path.write_text(fm_str + body, encoding="utf-8")

    return {
        "path": note_path,
        "summary": data.get("summary", ""),
        "tags": fm["tags"],
        "enriched": True,
    }
