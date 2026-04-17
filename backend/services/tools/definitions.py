"""Tool JSON definitions exposed to Claude via the Messages API."""

# ── Core tools ────────────────────────────────────────────────────────────────

CORE_TOOLS = [
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
    {
        "name": "query_graph",
        "description": "Query the knowledge graph to find related notes, people, tags, or topics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Entity to search for (note title, person, tag, topic)",
                },
                "relation_type": {
                    "type": "string",
                    "description": "Optional: filter by relation type",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to traverse",
                    "default": 1,
                },
            },
            "required": ["entity"],
        },
    },
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
    },
    {
        "name": "web_search",
        "description": (
            "Search the internet using DuckDuckGo. Use this when the user's notes "
            "do not contain enough information to answer the question. "
            "Always search notes first (search_notes) before using web_search."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in the language most likely to give good results",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]

# ── Jira tools ────────────────────────────────────────────────────────────────

JIRA_TOOLS = [
    {
        "name": "jira_list_issues",
        "description": (
            "List Jira issues from the local index. Supports facet filters "
            "(status, sprint, assignee, project, priority) and sorting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status category: to-do, in-progress, done",
                },
                "sprint": {
                    "type": "string",
                    "description": "Filter by sprint name",
                },
                "sprint_state": {
                    "type": "string",
                    "description": "Filter by sprint state: ACTIVE, CLOSED, FUTURE",
                },
                "assignee": {
                    "type": "string",
                    "description": "Filter by assignee display name",
                },
                "project_key": {
                    "type": "string",
                    "description": "Filter by project key (e.g. AUTH)",
                },
                "priority": {
                    "type": "string",
                    "description": "Filter by priority (High, Medium, Low)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (1-50)",
                    "default": 20,
                },
                "sort": {
                    "type": "string",
                    "description": "Sort field: updated, risk, priority",
                    "default": "updated",
                },
            },
            "required": [],
        },
    },
    {
        "name": "jira_describe_issue",
        "description": (
            "Get full details for a Jira issue: metadata, enrichment, "
            "hard links (blocks/depends_on), soft links, and related notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Issue key, e.g. AUTH-155",
                },
            },
            "required": ["key"],
        },
    },
    {
        "name": "jira_blockers_of",
        "description": (
            "Find all issues that block a given issue: direct blockers, "
            "transitive blockers (BFS, max depth 3), and likely blockers from soft edges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Issue key to find blockers for",
                },
            },
            "required": ["key"],
        },
    },
    {
        "name": "jira_depends_on",
        "description": (
            "Find all issues that depend on a given issue (what it blocks): "
            "direct dependents, transitive dependents (BFS, max depth 3)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Issue key to find dependents of",
                },
            },
            "required": ["key"],
        },
    },
    {
        "name": "jira_sprint_risk",
        "description": (
            "Analyse risk for a sprint: list issues with risk/ambiguity levels, "
            "find top risks, unclear tickets, and bottleneck assignees."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sprint_name": {
                    "type": "string",
                    "description": "Sprint name (defaults to active sprint if omitted)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "jira_cluster_by_topic",
        "description": (
            "Cluster issues by topic/business area using enrichment data. "
            "Optionally restrict to specific root issue keys."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "root_keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: restrict clustering to these issue keys and their neighbours",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Max clusters to return",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
]

# ── Combined list (backward compat) ──────────────────────────────────────────

TOOLS: list[dict] = CORE_TOOLS + JIRA_TOOLS
