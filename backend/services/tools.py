import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from services import memory_service, planning_service, preference_service


TOOLS = [
    {
        "name": "search_notes",
        "description": "Search the user's notes by keyword, tag, or topic. Returns matching note metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "folder": {"type": "string", "description": "Optional folder filter"},
                "limit": {
                    "type": "integer",
                    "description": "Max results",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_note",
        "description": "Read the full content of a specific note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Note path relative to memory/",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_note",
        "description": "Create or overwrite a note with Markdown content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Note path relative to memory/",
                },
                "content": {
                    "type": "string",
                    "description": "Full Markdown content with frontmatter",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_note",
        "description": "Append content to an existing note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Note path relative to memory/",
                },
                "content": {
                    "type": "string",
                    "description": "Content to append",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "create_plan",
        "description": "Create an organized plan from chaotic input. Saves as a Markdown note with checklist format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Plan title"},
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of items/tasks to organize",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for organizing",
                },
            },
            "required": ["title", "items"],
        },
    },
    {
        "name": "update_plan",
        "description": "Toggle a task checkbox in an existing plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Plan path relative to memory/",
                },
                "task_index": {
                    "type": "integer",
                    "description": "Zero-based index of the task to toggle",
                },
                "checked": {
                    "type": "boolean",
                    "description": "Whether to check or uncheck the task",
                },
            },
            "required": ["path", "task_index", "checked"],
        },
    },
    {
        "name": "summarize_context",
        "description": "Save a summary to memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Summary content"},
                "title": {"type": "string", "description": "Summary title"},
                "save": {
                    "type": "boolean",
                    "description": "Whether to save to memory",
                    "default": True,
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "save_preference",
        "description": "Save a user preference or rule for how Jarvis should behave.",
        "input_schema": {
            "type": "object",
            "properties": {
                "rule": {"type": "string", "description": "The preference or rule"},
                "category": {
                    "type": "string",
                    "description": "Category: style, sources, behavior, format",
                    "default": "general",
                },
            },
            "required": ["rule"],
        },
    },
]


class ToolNotFoundError(Exception):
    pass


async def execute_tool(
    name: str,
    tool_input: dict[str, Any],
    workspace_path: Optional[Path] = None,
) -> str:
    """Execute a tool by name and return string result."""
    if name == "search_notes":
        results = await memory_service.list_notes(
            folder=tool_input.get("folder"),
            search=tool_input["query"],
            limit=tool_input.get("limit", 10),
            workspace_path=workspace_path,
        )
        return json.dumps(results)

    if name == "read_note":
        note = await memory_service.get_note(
            tool_input["path"],
            workspace_path=workspace_path,
        )
        return note["content"]

    if name == "write_note":
        await memory_service.create_note(
            tool_input["path"],
            tool_input["content"],
            workspace_path=workspace_path,
        )
        return f"Note saved: {tool_input['path']}"

    if name == "append_note":
        await memory_service.append_note(
            tool_input["path"],
            tool_input["content"],
            workspace_path=workspace_path,
        )
        return f"Content appended to: {tool_input['path']}"

    if name == "create_plan":
        result = await planning_service.create_plan(
            tool_input["title"],
            tool_input["items"],
            workspace_path=workspace_path,
        )
        return json.dumps(result)

    if name == "update_plan":
        content = await planning_service.update_plan_task(
            tool_input["path"],
            tool_input["task_index"],
            tool_input["checked"],
            workspace_path=workspace_path,
        )
        return content

    if name == "summarize_context":
        return _execute_summarize(tool_input, workspace_path)

    if name == "save_preference":
        category = tool_input.get("category", "general")
        preference_service.save_preference(
            category,
            tool_input["rule"],
            workspace_path=workspace_path,
        )
        return f"Preference saved: [{category}] {tool_input['rule']}"

    raise ToolNotFoundError(f"Unknown tool: {name}")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _execute_summarize(
    tool_input: dict[str, Any],
    workspace_path: Optional[Path],
) -> str:
    content = tool_input["content"]
    title = tool_input.get("title", "summary")
    save = tool_input.get("save", True)

    if not save:
        return content

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    note_path = f"summaries/{date}-{slug}.md"

    fm = (
        f"---\ntitle: {title}\ntype: summary\n"
        f"source: conversation\ntags: [summary]\n---\n\n"
    )
    full = fm + content

    mem = (workspace_path or Path.home() / "Jarvis") / "memory"
    target = mem / note_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(full, encoding="utf-8")

    return json.dumps({"path": note_path, "saved": True})
