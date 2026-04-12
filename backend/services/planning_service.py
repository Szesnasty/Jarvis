import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings
from services import memory_service
from utils.markdown import parse_frontmatter


def _memory_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def create_plan(
    title: str,
    items: List[str],
    workspace_path: Optional[Path] = None,
) -> Dict:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(title)
    note_path = f"plans/{date}-{slug}.md"

    checkboxes = "\n".join(f"- [ ] {item}" for item in items)
    content = (
        f"---\ntitle: {title}\ntags: [plan]\ntype: plan\n---\n\n"
        f"## Today\n\n{checkboxes}\n\n"
        f"## This Week\n\n\n\n"
        f"## Later\n\n"
    )

    await memory_service.create_note(note_path, content, workspace_path)
    full_content = (_memory_path(workspace_path) / note_path).read_text(encoding="utf-8")
    return {"path": note_path, "content": full_content}


async def update_plan_task(
    note_path: str,
    task_index: int,
    checked: bool,
    workspace_path: Optional[Path] = None,
) -> str:
    memory_service._validate_path(note_path)
    mem = _memory_path(workspace_path)
    file_path = mem / note_path

    if not file_path.exists():
        raise memory_service.NoteNotFoundError(f"Plan not found: {note_path}")

    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    count = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            if count == task_index:
                if checked:
                    lines[i] = line.replace("- [ ]", "- [x]")
                else:
                    lines[i] = line.replace("- [x]", "- [ ]")
                break
            count += 1

    new_content = "\n".join(lines)
    file_path.write_text(new_content, encoding="utf-8")
    return new_content


async def list_plans(workspace_path: Optional[Path] = None) -> List[Dict]:
    results = await memory_service.list_notes(folder="plans", workspace_path=workspace_path)
    results.sort(key=lambda r: r["path"], reverse=True)
    return results


async def get_plan(note_path: str, workspace_path: Optional[Path] = None) -> str:
    note = await memory_service.get_note(note_path, workspace_path=workspace_path)
    return note["content"]
