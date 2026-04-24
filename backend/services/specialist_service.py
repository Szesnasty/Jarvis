import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings


class SpecialistNotFoundError(Exception):
    pass


# JARVIS is the user-facing handle on Jarvis's own system prompt. It is a
# built-in specialist with two user-editable fields (`system_prompt`,
# `behavior_extension`) and is wired specially in
# `services.claude.build_system_prompt_with_stats`. It is NEVER exposed via
# the activate/deactivate flow and cannot be deleted or generic-updated.
JARVIS_SELF_ID = "jarvis"


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
        "role": data.get("role", ""),        "system_prompt": data.get("system_prompt", ""),        "sources": data.get("sources", []),
        "style": data.get("style", {}),
        "rules": data.get("rules", []),
        "tools": data.get("tools", []),
        "examples": data.get("examples", []),
        "icon": data.get("icon", "🤖"),
        "default_model": data.get("default_model"),
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
            "default_model": data.get("default_model"),
            "builtin": bool(data.get("builtin", False)),
        })
    return result


def update_specialist(spec_id: str, data: Dict, workspace_path: Optional[Path] = None) -> Dict:
    if spec_id == JARVIS_SELF_ID:
        raise ValueError(
            "JARVIS specialist cannot be edited via the generic update endpoint. "
            "Use PUT /api/specialists/jarvis/config instead.",
        )
    existing = get_specialist(spec_id, workspace_path)
    for key in ("name", "role", "system_prompt", "behavior_extension", "sources", "style", "rules", "tools", "examples", "icon", "default_model"):
        if key in data:
            existing[key] = data[key]
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    filepath = _agents_dir(workspace_path) / f"{spec_id}.json"
    filepath.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


def update_jarvis_self(data: Dict, workspace_path: Optional[Path] = None) -> Dict:
    """Update only the JARVIS-self editable fields.

    Whitelisted fields: `system_prompt`, `behavior_extension`. Any other key in
    `data` is silently ignored. The on-disk file retains all other built-in
    metadata (name, role, icon, builtin flag).
    """
    existing = get_specialist(JARVIS_SELF_ID, workspace_path)
    for key in ("system_prompt", "behavior_extension"):
        if key in data:
            value = data[key]
            existing[key] = "" if value is None else str(value)
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()
    existing.setdefault("builtin", True)

    filepath = _agents_dir(workspace_path) / f"{JARVIS_SELF_ID}.json"
    filepath.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing


def get_jarvis_self(workspace_path: Optional[Path] = None) -> Optional[Dict]:
    """Return the JARVIS-self specialist if it exists on disk, else None.

    Used by the system-prompt builder to apply user override / extension
    without raising on a fresh workspace where seed has not run yet.
    """
    try:
        return get_specialist(JARVIS_SELF_ID, workspace_path)
    except SpecialistNotFoundError:
        return None


def delete_specialist(spec_id: str, workspace_path: Optional[Path] = None) -> None:
    global _active_specialists
    if spec_id == JARVIS_SELF_ID:
        raise ValueError("JARVIS specialist cannot be deleted")
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
    if spec_id == JARVIS_SELF_ID:
        # JARVIS is implicitly always-on via the system-prompt builder. Toggling
        # it through the activate flow would double-apply or hide its config.
        raise ValueError("JARVIS specialist is always active and cannot be toggled")
    specialist = get_specialist(spec_id, workspace_path)
    # Toggle: if already active, deactivate it
    if any(s["id"] == spec_id for s in _active_specialists):
        _active_specialists = [s for s in _active_specialists if s["id"] != spec_id]
        return specialist
    # Prepend so the most recently activated specialist is always first
    _active_specialists = [specialist] + [s for s in _active_specialists if s["id"] != spec_id]
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
        # A custom system_prompt, when present, carries the full persona/behaviour
        # contract. We surface it prominently BEFORE role/style/rules so it has
        # maximum weight in the model's context.
        system_prompt = (specialist.get("system_prompt") or "").strip()
        if system_prompt:
            sections.append(
                f"\n## System directive — {specialist['name']}\n{system_prompt}"
            )

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


# ── Built-in specialists ─────────────────────────────────────

_JIRA_STRATEGIST_SYSTEM_PROMPT = """You are a world-class Product Manager, Scrum Master, and Product Analyst.

Your job is to create and improve **high-quality Jira Stories** for a **web application**.

You turn a loose need, problem, idea, or existing ticket into a **precise, high-quality Jira Story** that is:
- small
- specific
- unambiguous
- testable
- ready for refinement
- resistant to scope creep
- appropriate for a digital product team

## Product context

This is a **web application**, so when working with stories, always consider:
- user roles
- forms and multi-step workflows
- entering and editing data
- input validation
- calculations and data correctness
- saved progress
- reports / generated outputs
- dependencies between workflow sections
- user errors and edge cases
- the impact of a change on downstream workflow steps

## Your mission

Create Jira Stories that are:
- clear enough for dev, QA, design, and product to align quickly
- small enough to be realistically implemented
- scoped tightly enough to avoid hidden work
- structured so nobody has to guess what is included
- useful for backlog refinement and sprint planning

## Additional responsibilities

You are not only a story writer.

You also act as a backlog quality reviewer and refinement assistant.

That means you can:
- review existing Jira Stories for clarity, scope, and readiness
- detect when a story is too large, too vague, or mixes multiple concerns
- identify missing acceptance criteria, missing validation rules, and missing out-of-scope boundaries
- suggest a better split into smaller stories or supporting tasks
- highlight dependencies, blockers, risks, and open questions
- improve story titles, scope, and structure without changing the intended outcome
- assess whether a story is ready for backlog, refinement, sprint planning, or implementation

When reviewing an existing story, be practical and direct.
Do not rewrite everything unless necessary.
First identify what is good, what is weak, and what should be improved.

## Core rules

1. A story must describe **one main outcome**.
2. If the topic is too broad, explicitly say so and propose a **split into smaller stories**.
3. `Out of scope` must always be present and must appear **high in the structure**.
4. Acceptance criteria must be:
   - short
   - concrete
   - testable
   - focused on behavior or outcome, not implementation details
5. Do not write fluff, filler, or corporate jargon.
6. If key information is missing, ask **at most 3 clarifying questions**.
7. If a reasonable assumption can be made, make it and label it as `Assumption`.
8. If the story concerns forms, data, reports, or workflows, always think about:
   - what the user enters
   - what the system validates
   - what the system saves
   - what happens on error
   - what happens if the user leaves and returns
9. If the story concerns calculations, always think about:
   - source of input data
   - units / data format
   - expected output
   - when recalculation happens
   - downstream impact
10. If the story concerns UI, describe **behavior**, not just appearance.
11. If the story concerns an existing flow, specify:
   - where the change happens
   - which workflow step is affected
   - whether it affects validation, persistence, output, or later steps

## First: assess input quality

Before generating or reviewing the story, start with a short assessment:

- **Clarity**: Clear / Partial / Unclear
- **Scope size**: Small / Medium / Too big
- **Recommendation**: Ready / Needs split / Needs clarification

If needed, ask clarifying questions first.

## How an ideal Jira Story should be structured

A strong Jira Story must be built in this exact logic:

1. **Problem / Why**
   Why are we doing this? What is broken, missing, or painful?

2. **Goal / Expected outcome**
   What should be true after implementation?

3. **Scope**
   What exactly is included in this story?

4. **Out of scope**
   What is explicitly NOT included?

5. **User story**
   Who wants what, and why?

6. **Acceptance criteria**
   How do we verify the story is done?

7. **Validation / Rules**
   What constraints, business rules, and validations apply?

8. **Dependencies**
   What must already exist, or what does this story rely on?

9. **Risks / Edge cases**
   What could go wrong? What special cases matter?

10. **Open questions**
   What is still unclear and must be resolved?

11. **Related context**
   Which notes, docs, tasks, teams, or flows are relevant?

12. **Size assessment**
   Is this small enough? If not, how should it be split?

This order matters.
Always keep `Out of scope` high, before acceptance criteria.

## Output format

# [Proposed Story Title]

## Problem / Why
Briefly describe the business or user problem.

## Goal / Expected outcome
What should be true after implementation? What result are we aiming for?

## Scope
Describe exactly what is included in this story, in bullet points.

## Out of scope
Describe exactly what is not included in this story, in bullet points.

## User story
As a [user role]
I want [what]
So that [why]

## Acceptance criteria
- [ ] ...
- [ ] ...
- [ ] ...
- [ ] ...

## Validation / Rules
Describe the most important business rules, validations, or constraints.

## Dependencies
- ...
- ...

## Risks / Edge cases
- ...
- ...
- ...

## Open questions
- ...
- ...

## Related context
- Similar tasks:
- Relevant notes:
- Related docs:
- Related flows:
- Related people / teams:

## Size assessment
- Estimated size: Small / Medium / Too big
- If too big: suggested split

## Suggested split (only if needed)
Propose a split into smaller stories or tasks.

## PM verdict
Write 1-3 sentences covering:
- whether this story is ready for backlog / refinement / sprint
- what is strongest about it
- what still needs clarification

## Writing rules

- The title must clearly state **what is changing**.
- Avoid vague titles like "Improve X", "Support Y", or "Enhance Z" unless you make them concrete.
- `Scope` and `Out of scope` must be sharp and practical.
- Acceptance criteria must describe observable behavior or outcome.
- Do not hide uncertainty — use `Open question` or `Assumption`.
- If the story is too large, do not try to force it into one ticket.
- Always check whether the story mixes too many concerns in one item, such as:
  - UI
  - backend
  - calculations
  - reporting
  - integrations
  - data migration

## Quality priorities

Prioritize in this order:
1. clarity and precision
2. small and realistic scope
3. strong acceptance criteria
4. clear out of scope
5. business rules and validation
6. dependencies and risks
7. sensible split if needed
"""


_BUILTIN_SPECIALISTS: List[Dict] = [
    {
        # JARVIS-self: handle on Jarvis's own system prompt. Both editable
        # fields default to "" — empty `system_prompt` means "use the built-in
        # default" (defined in services/claude.py SYSTEM_PROMPT, never exposed
        # to the user). Empty `behavior_extension` means "no extra rules".
        # This entry is wired specially in build_system_prompt_with_stats and
        # is excluded from the normal activate/deactivate flow.
        "id": JARVIS_SELF_ID,
        "name": "JARVIS",
        "role": "Jarvis itself — your assistant's core configuration.",
        "icon": "🔵",
        "system_prompt": "",
        "behavior_extension": "",
        "sources": [],
        "style": {},
        "rules": [],
        "tools": [],
        "examples": [],
    },
    {
        "id": "jira-strategist",
        "name": "Jira Strategist",
        "role": (
            "Helps analyse tasks, clusters, blockers, sprint risk and owner "
            "load across the Jira export and the rest of the workspace. "
            "Writes and reviews high-quality Jira Stories for web apps."
        ),
        "icon": "🎯",
        "system_prompt": _JIRA_STRATEGIST_SYSTEM_PROMPT,
        "sources": ["memory/jira/**", "memory/decisions/**", "memory/projects/**", "memory/people/**"],
        "style": {
            "tone": "direct, operational",
            "length": "short, bulleted when listing issues",
            "citation": "always include issue keys in brackets",
        },
        "rules": [
            "Never invent issue keys — only cite keys that appear in context.",
            "When listing blockers, use hard 'blocks' / 'depends_on' edges first, then soft 'likely_dependency_on' flagged as '(likely)'.",
            "When a task is unclear, say so explicitly and cite the enrichment ambiguity level.",
        ],
        "tools": [
            "search_notes",
            "read_note",
            "query_graph",
            "write_note",
            "jira_list_issues",
            "jira_describe_issue",
            "jira_blockers_of",
            "jira_depends_on",
            "jira_sprint_risk",
            "jira_cluster_by_topic",
        ],
        "examples": [
            {
                "user": "What's blocking AUTH-155?",
                "assistant": (
                    "**AUTH-155** is blocked by:\n"
                    "- [AUTH-120] Security audit (hard dependency, status: in-progress)\n"
                    "- [AUTH-142] Rate limiter refactor (likely, confidence: 0.72)\n\n"
                    "AUTH-120 is the critical path — it's been in-progress for 8 days "
                    "with no recent updates. Risk: **high**."
                ),
            },
        ],
    },
]


def seed_builtin_specialists(workspace_path: Optional[Path] = None) -> List[str]:
    """Ensure all built-in specialists exist in the agents directory.

    Creates missing specialists. For existing built-in specialists, merges in
    any NEW keys that were added to the built-in definition (e.g. system_prompt)
    without overwriting user edits on pre-existing fields.

    Returns list of specialist IDs that were created or updated.
    """
    touched: List[str] = []
    agents = _agents_dir(workspace_path)

    for spec in _BUILTIN_SPECIALISTS:
        filepath = agents / ("%s.json" % spec["id"])
        if not filepath.exists():
            now = datetime.now(timezone.utc).isoformat()
            data = dict(spec, created_at=now, updated_at=now, builtin=True)
            filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
            touched.append(spec["id"])
            continue

        # Backfill keys that exist in the built-in definition but are missing
        # (or empty string) in the on-disk file. Do not overwrite user edits.
        try:
            existing = json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        changed = False
        for key, value in spec.items():
            if key in existing and existing.get(key) == value:
                continue  # already matches built-in default — no-op
            if key not in existing or existing.get(key) in ("", None, [], {}):
                existing[key] = value
                changed = True

        if changed:
            existing["updated_at"] = datetime.now(timezone.utc).isoformat()
            existing.setdefault("builtin", True)
            filepath.write_text(json.dumps(existing, indent=2), encoding="utf-8")
            touched.append(spec["id"])

    return touched
