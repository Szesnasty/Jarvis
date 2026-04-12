import json
from pathlib import Path
from typing import Any, Optional

from services import memory_service


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

    raise ToolNotFoundError(f"Unknown tool: {name}")
