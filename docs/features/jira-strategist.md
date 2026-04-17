# Jira Strategist

> Built-in specialist for analysing Jira tasks, blockers, sprint risk
> and cross-source connections.

## Summary

**Jira Strategist** is the first built-in specialist shipped with
Jarvis.  It is automatically seeded into the `agents/` directory on
workspace creation and on startup (for existing workspaces).

It is designed to help users reason about their Jira projects by
grounding answers in the indexed truth — never inventing issue keys.

## How It Works

### Seeding

`seed_builtin_specialists()` in `specialist_service.py` checks the
`agents/` directory and creates `jira-strategist.json` if it does not
already exist.  The function is called:

1. During `create_workspace()` in `workspace_service.py`
2. During app startup in `main.py` (lifespan hook)

It never overwrites a user-edited file — if the file exists, it is
skipped.  The `builtin: true` flag in the JSON marks it as system-seeded.

### Profile

| Field | Value |
|-------|-------|
| **ID** | `jira-strategist` |
| **Name** | Jira Strategist |
| **Icon** | 🎯 |
| **Tone** | direct, operational |
| **Length** | short, bulleted when listing issues |
| **Citation** | always include issue keys in brackets |

### Rules

1. Never invent issue keys — only cite keys that appear in context.
2. When listing blockers, use hard edges first, soft edges flagged as *(likely)*.
3. When a task is unclear, say so explicitly and cite the enrichment ambiguity level.

### Knowledge scope

Sources: `memory/jira/**`, `memory/decisions/**`, `memory/projects/**`

## Key Files

| File | Role |
|------|------|
| [specialist_service.py](../../backend/services/specialist_service.py) | `_BUILTIN_SPECIALISTS` list + `seed_builtin_specialists()` |
| [workspace_service.py](../../backend/services/workspace_service.py) | Calls seeding during workspace creation |
| [main.py](../../backend/main.py) | Calls seeding on startup |
