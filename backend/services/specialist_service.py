import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings


class SpecialistNotFoundError(Exception):
    pass


_active_specialist: Optional[Dict] = None


def _agents_dir(workspace_path: Optional[Path] = None) -> Path:
    d = (workspace_path or get_settings().workspace_path) / "agents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _trash_dir(workspace_path: Optional[Path] = None) -> Path:
    d = (workspace_path or get_settings().workspace_path) / ".trash"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def create_specialist(data: Dict, workspace_path: Optional[Path] = None) -> Dict:
    name = data.get("name", "").strip()
    if not name:
        raise ValueError("Specialist name is required")

    spec_id = data.get("id") or _slugify(name)
    now = datetime.now(timezone.utc).isoformat()

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

    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    filepath.write_text(json.dumps(specialist, indent=2), encoding="utf-8")
    return specialist


def get_specialist(spec_id: str, workspace_path: Optional[Path] = None) -> Dict:
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
    global _active_specialist
    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    if not filepath.exists():
        raise SpecialistNotFoundError(f"Specialist not found: {spec_id}")

    if _active_specialist and _active_specialist.get("id") == spec_id:
        _active_specialist = None

    trash = _trash_dir(workspace_path)
    dest = trash / f"{spec_id}.json"
    shutil.move(str(filepath), str(dest))


def activate_specialist(spec_id: str, workspace_path: Optional[Path] = None) -> Dict:
    global _active_specialist
    specialist = get_specialist(spec_id, workspace_path)
    _active_specialist = specialist
    return specialist


def deactivate_specialist() -> None:
    global _active_specialist
    _active_specialist = None


def get_active_specialist() -> Optional[Dict]:
    return _active_specialist


def build_specialist_prompt(specialist: Dict, base_prompt: str) -> str:
    sections = [base_prompt]

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
        sections.append(f"\nRules you MUST follow:\n{rules_str}")

    examples = specialist.get("examples", [])
    for ex in examples[:2]:
        sections.append(f"\nExample:\nUser: {ex['user']}\nAssistant: {ex['assistant']}")

    return "\n".join(sections)


def filter_tools(tools: List[Dict], specialist: Optional[Dict]) -> List[Dict]:
    if not specialist:
        return tools
    allowed = specialist.get("tools", [])
    if not allowed:
        return tools
    return [t for t in tools if t["name"] in allowed]


def suggest_specialist(
    user_message: str,
    workspace_path: Optional[Path] = None,
) -> Optional[Dict]:
    specialists = list_specialists(workspace_path)
    if not specialists:
        return None

    msg_lower = user_message.lower()
    for spec_meta in specialists:
        try:
            spec = get_specialist(spec_meta["id"], workspace_path)
        except SpecialistNotFoundError:
            continue
        keywords = [spec["name"].lower()]
        keywords.extend(s.lower() for s in spec.get("sources", []))
        keywords.extend(spec.get("role", "").lower().split())
        for kw in keywords:
            if kw and kw in msg_lower:
                return spec_meta
    return None


def reset_state() -> None:
    global _active_specialist
    _active_specialist = None
