---
title: Planning Service
status: active
type: feature
sources:
  - backend/services/planning_service.py
depends_on: [retrieval, chat]
last_reviewed: 2026-04-14
---

# Planning Service

## Summary

The planning service creates and manages checklist-style plan notes inside `memory/plans/`. It is not a standalone endpoint — Claude invokes it as a tool during chat when the user asks to organize tasks or brain dumps into an actionable plan. Plans are plain Markdown files with standard frontmatter, so they are fully readable in Obsidian and survive any database loss.

## How It Works

When Claude decides to call the `create_plan` tool, the chat pipeline delegates to `planning_service.create_plan()`. The service generates a date-prefixed, slug-derived filename (e.g. `plans/2026-04-14-weekly-review.md`) and writes a Markdown file with three pre-structured sections: **Today**, **This Week**, and **Later**. The user-supplied task items are placed under "Today" as unchecked GFM checkboxes (`- [ ] ...`). The file is written through `memory_service.create_note`, so path validation and directory creation follow the same rules as all other memory writes.

Checkbox state is updated in-place by `update_plan_task`. Rather than re-parsing the Markdown with a library, it walks the file line-by-line counting checkbox lines (both `- [ ]` and `- [x]` are counted) and replaces the substring at the zero-based `task_index`. This means the index is positional across the entire file, not scoped to a section — all checkboxes regardless of heading contribute to the count.

`list_plans` delegates to `memory_service.list_notes(folder="plans")` and then sorts the returned list by path in descending order. Because filenames are date-prefixed with ISO 8601 format, lexicographic sort is equivalent to date sort, so the most recent plans surface first with no date parsing required.

`get_plan` is a thin wrapper around `memory_service.get_note` that returns only the content string, discarding the metadata dict the lower-level function returns.

The service has no HTTP router of its own. The only way to trigger plan creation or task toggling from the frontend is through the chat WebSocket, which causes Claude to emit a `tool_use` block. The `session_service` also uses the tool name `"create_plan"` as a signal to tag saved sessions with the `"planning"` tag.

## Key Files

- `backend/services/planning_service.py` — All plan CRUD logic: create, read, list, and in-place checkbox toggle.
- `backend/services/tools.py` — Defines the `create_plan` and `update_plan` tool schemas that Claude sees, and dispatches tool calls to the planning service.
- `backend/services/session_service.py` — Maps tool names to session tags; `create_plan` and `update_plan` both map to the `"planning"` tag.

## API / Interface

These are internal Python functions, not HTTP endpoints. They are called exclusively via the tool dispatch layer in `backend/services/tools.py`.

```python
async def create_plan(
    title: str,
    items: List[str],
    workspace_path: Optional[Path] = None,
) -> Dict:
    # Returns {"path": "plans/YYYY-MM-DD-slug.md", "content": "<full file text>"}

async def update_plan_task(
    note_path: str,
    task_index: int,   # zero-based index across ALL checkboxes in the file
    checked: bool,
    workspace_path: Optional[Path] = None,
) -> str:
    # Returns the full updated file content as a string

async def list_plans(workspace_path: Optional[Path] = None) -> List[Dict]:
    # Returns list of plan note metadata dicts, newest first

async def get_plan(note_path: str, workspace_path: Optional[Path] = None) -> str:
    # Returns plan file content as a string
```

The `create_plan` tool definition also accepts a `context` field (a free-text string Claude may pass for additional context), but `planning_service.create_plan` ignores it — the tools dispatcher does not forward it. It exists solely to guide Claude's reasoning about when to call the tool.

## Gotchas

**Checkbox indexing is file-global, not section-local.** `update_plan_task` counts every `- [ ]` or `- [x]` line in the file to find `task_index`. If a plan has checkboxes in multiple sections (Today, This Week, Later), the index spans all of them. A `task_index` of 3 means the fourth checkbox in the entire file, not the fourth item under a particular heading.

**`context` is silently dropped.** The `create_plan` tool schema exposes a `context` parameter, but `tools.py` does not pass it to `planning_service.create_plan`, which does not accept it. If you add context-aware plan generation later, both the service signature and the dispatcher need to be updated.

**No direct HTTP endpoint.** There is no `/plans` REST route. Reads, writes, and toggles can only be triggered through the chat tool pipeline. If you need to expose plans to the frontend independently (e.g. a dedicated plans UI), a router will need to be added and wired into `main.py`.

**Slug collisions on same-day creation.** Two plans created on the same day with the same title produce the same filename. `memory_service.create_note` will overwrite the earlier file without warning.
