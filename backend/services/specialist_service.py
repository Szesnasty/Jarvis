import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings


class SpecialistNotFoundError(Exception):
    pass


_active_specialists: List[Dict] = []


def _agents_dir(workspace_path: Optional[Path] = None) -> Path:
    d = (workspace_path or get_settings().workspace_path) / "agents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _trash_dir(workspace_path: Optional[Path] = None) -> Path:
    d = (workspace_path or get_settings().workspace_path) / ".trash"
    d.mkdir(parents=True, exist_ok=True)
    return d


_SPEC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,63}$")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _validate_spec_id(spec_id: str) -> None:
    """Validate specialist ID to prevent path traversal."""
    if not _SPEC_ID_RE.match(spec_id):
        raise ValueError(f"Invalid specialist id: {spec_id!r}")


def create_specialist(data: Dict, workspace_path: Optional[Path] = None) -> Dict:
    name = data.get("name", "").strip()
    if not name:
        raise ValueError("Specialist name is required")

    spec_id = data.get("id") or _slugify(name)
    _validate_spec_id(spec_id)
    now = datetime.now(timezone.utc).isoformat()

    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    if filepath.exists():
        raise ValueError(f"A specialist with id '{spec_id}' already exists")

    specialist = {
        "id": spec_id,
        "name": name,
        "role": data.get("role", ""),
        "sources": data.get("sources", []),
        "style": data.get("style", {}),
        "rules": data.get("rules", []),
        "tools": data.get("tools", []),
        "examples": data.get("examples", []),
        "icon": data.get("icon", "🤖"),
        "created_at": now,
        "updated_at": now,
    }

    filepath.write_text(json.dumps(specialist, indent=2), encoding="utf-8")
    return specialist


def get_specialist(spec_id: str, workspace_path: Optional[Path] = None) -> Dict:
    _validate_spec_id(spec_id)
    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    if not filepath.exists():
        raise SpecialistNotFoundError(f"Specialist not found: {spec_id}")
    return json.loads(filepath.read_text(encoding="utf-8"))


def list_specialists(workspace_path: Optional[Path] = None) -> List[Dict]:
    d = _agents_dir(workspace_path)
    result = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        result.append({
            "id": data["id"],
            "name": data["name"],
            "icon": data.get("icon", "🤖"),
            "source_count": len(data.get("sources", [])),
            "rule_count": len(data.get("rules", [])),
            "file_count": count_specialist_files(data["id"], workspace_path),
        })
    return result


def update_specialist(spec_id: str, data: Dict, workspace_path: Optional[Path] = None) -> Dict:
    existing = get_specialist(spec_id, workspace_path)
    for key in ("name", "role", "sources", "style", "rules", "tools", "examples", "icon"):
        if key in data:
            existing[key] = data[key]
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    filepath.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


def delete_specialist(spec_id: str, workspace_path: Optional[Path] = None) -> None:
    global _active_specialists
    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    if not filepath.exists():
        raise SpecialistNotFoundError(f"Specialist not found: {spec_id}")

    _active_specialists = [s for s in _active_specialists if s.get("id") != spec_id]

    trash = _trash_dir(workspace_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest = trash / f"{spec_id}-{stamp}.json"
    shutil.move(str(filepath), str(dest))

    # Clean up knowledge-files directory
    files_dir = _agents_dir(workspace_path) / spec_id
    if files_dir.is_dir():
        shutil.rmtree(str(files_dir))


def activate_specialist(spec_id: str, workspace_path: Optional[Path] = None) -> Dict:
    global _active_specialists
    specialist = get_specialist(spec_id, workspace_path)
    # Toggle: if already active, deactivate it
    if any(s["id"] == spec_id for s in _active_specialists):
        _active_specialists = [s for s in _active_specialists if s["id"] != spec_id]
        return specialist
    _active_specialists.append(specialist)
    return specialist


def deactivate_specialist(spec_id: Optional[str] = None) -> None:
    global _active_specialists
    if spec_id:
        _active_specialists = [s for s in _active_specialists if s["id"] != spec_id]
    else:
        _active_specialists = []


def get_active_specialist() -> Optional[Dict]:
    """Return first active specialist for backward compatibility."""
    return _active_specialists[0] if _active_specialists else None


def get_active_specialists() -> List[Dict]:
    return list(_active_specialists)


def build_specialist_prompt(specialist: Dict, base_prompt: str) -> str:
    """Build prompt for a single specialist (backward compat)."""
    return build_multi_specialist_prompt([specialist], base_prompt)


def build_multi_specialist_prompt(specialists: List[Dict], base_prompt: str) -> str:
    sections = [base_prompt]

    for specialist in specialists:
        sections.append(f"\n## Active Specialist: {specialist['name']}\n{specialist.get('role', '')}")

        style = specialist.get("style", {})
        if style:
            parts = []
            if style.get("tone"):
                parts.append(f"Tone: {style['tone']}")
            if style.get("format"):
                parts.append(f"Format: {style['format']}")
            if style.get("length"):
                parts.append(f"Length: {style['length']}")
            if parts:
                sections.append(f"\nResponse style: {'. '.join(parts)}.")

        rules = specialist.get("rules", [])
        if rules:
            rules_str = "\n".join(f"- {r}" for r in rules)
            sections.append(f"\nRules you MUST follow ({specialist['name']}):\n{rules_str}")

        examples = specialist.get("examples", [])
        for ex in examples[:2]:
            sections.append(f"\nExample ({specialist['name']}):\nUser: {ex['user']}\nAssistant: {ex['assistant']}")

    return "\n".join(sections)


def filter_tools(tools: List[Dict], specialist: Optional[Dict] = None, specialists: Optional[List[Dict]] = None) -> List[Dict]:
    """Filter tools for active specialists. Union of all allowed tools."""
    specs = specialists or ([specialist] if specialist else [])
    if not specs:
        return tools
    # Collect allowed tools from all active specialists
    all_allowed = set()
    has_restrictions = False
    for s in specs:
        allowed = s.get("tools", [])
        if allowed:
            has_restrictions = True
            all_allowed.update(allowed)
    if not has_restrictions:
        return tools
    return [t for t in tools if t["name"] in all_allowed]


def suggest_specialist(
    user_message: str,
    workspace_path: Optional[Path] = None,
) -> Optional[Dict]:
    specialists = list_specialists(workspace_path)
    if not specialists:
        return None

    _STOP_WORDS = {
        "a", "an", "the", "is", "are", "you", "your", "and", "or", "for",
        "to", "of", "in", "on", "with", "as", "at", "by", "from", "that",
        "this", "it", "be", "do", "have", "will", "can", "who", "what",
        "general", "assistant", "specialist", "help", "use", "make",
    }
    msg_lower = user_message.lower()
    for spec_meta in specialists:
        try:
            spec = get_specialist(spec_meta["id"], workspace_path)
        except SpecialistNotFoundError:
            continue
        # Include full name and individual name words
        name_lower = spec["name"].lower()
        keywords = [name_lower]
        keywords.extend(w for w in name_lower.split() if len(w) >= 3 and w not in _STOP_WORDS)
        keywords.extend(s.lower() for s in spec.get("sources", []))
        # Only use role words that are 4+ chars and not stop words
        role_words = [w for w in spec.get("role", "").lower().split()
                      if len(w) >= 4 and w not in _STOP_WORDS]
        keywords.extend(role_words)
        for kw in keywords:
            if kw and len(kw) >= 3 and kw in msg_lower:
                return spec_meta
    return None


def _files_dir(spec_id: str, workspace_path: Optional[Path] = None) -> Path:
    """Return the knowledge-files directory for a specialist."""
    _validate_spec_id(spec_id)
    d = _agents_dir(workspace_path) / spec_id
    d.mkdir(parents=True, exist_ok=True)
    return d


_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\- ]{0,200}$")
_ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf", ".csv", ".json"}


def _validate_filename(filename: str) -> None:
    """Validate filename to prevent path traversal and restrict to allowed types."""
    if not _SAFE_FILENAME_RE.match(filename):
        raise ValueError(f"Invalid filename: {filename!r}")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise ValueError(f"Invalid filename: {filename!r}")
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")


def list_specialist_files(spec_id: str, workspace_path: Optional[Path] = None) -> List[Dict]:
    """List all knowledge files for a specialist."""
    # Verify specialist exists
    get_specialist(spec_id, workspace_path)
    files_dir = _agents_dir(workspace_path) / spec_id
    if not files_dir.exists():
        return []
    result = []
    for f in sorted(files_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in _ALLOWED_EXTENSIONS:
            stat = f.stat()
            result.append({
                "filename": f.name,
                "path": f.name,
                "title": f.stem.replace("-", " ").replace("_", " "),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
            })
    return result


def save_specialist_file(spec_id: str, filename: str, content: bytes, workspace_path: Optional[Path] = None) -> Dict:
    """Save an uploaded file to a specialist's knowledge directory."""
    get_specialist(spec_id, workspace_path)
    _validate_filename(filename)
    files_dir = _files_dir(spec_id, workspace_path)
    target = files_dir / filename

    # Avoid overwriting — append number if exists
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        i = 1
        while target.exists():
            target = files_dir / f"{stem}-{i}{suffix}"
            i += 1

    target.write_bytes(content)
    stat = target.stat()
    return {
        "filename": target.name,
        "path": target.name,
        "title": target.stem.replace("-", " ").replace("_", " "),
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
    }


def delete_specialist_file(spec_id: str, filename: str, workspace_path: Optional[Path] = None) -> None:
    """Delete a file from a specialist's knowledge directory."""
    get_specialist(spec_id, workspace_path)
    _validate_filename(filename)
    files_dir = _agents_dir(workspace_path) / spec_id
    target = files_dir / filename
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {filename}")
    target.unlink()


def copy_file_to_specialist(spec_id: str, source_path: Path, title: str = "", workspace_path: Optional[Path] = None) -> Dict:
    """Copy an existing file into a specialist's knowledge directory."""
    get_specialist(spec_id, workspace_path)
    files_dir = _files_dir(spec_id, workspace_path)
    dest = files_dir / source_path.name
    # Avoid overwriting
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        i = 1
        while dest.exists():
            dest = files_dir / f"{stem}-{i}{suffix}"
            i += 1
    shutil.copy2(str(source_path), str(dest))
    stat = dest.stat()
    return {
        "filename": dest.name,
        "path": dest.name,
        "title": title or dest.stem.replace("-", " ").replace("_", " "),
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
    }


def count_specialist_files(spec_id: str, workspace_path: Optional[Path] = None) -> int:
    """Count knowledge files for a specialist."""
    files_dir = _agents_dir(workspace_path) / spec_id
    if not files_dir.exists():
        return 0
    return sum(1 for f in files_dir.iterdir() if f.is_file() and f.suffix.lower() in _ALLOWED_EXTENSIONS)


def reset_state() -> None:
    global _active_specialists
    _active_specialists = []
