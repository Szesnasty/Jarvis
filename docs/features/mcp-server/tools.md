# MCP Tools Reference

Complete catalogue of tools exposed by the Jarvis MCP server over `stdio`.
Any MCP-aware client (Claude Desktop, Cursor, VS Code Copilot, Continue, Zed, …)
can call these tools once `jarvis-mcp` is configured.

**23 read-only tools** are registered by default.
**3 additional write tools** are registered only when `mcp.allow_writes: true`
is set in `app/config.json` — for a total of **26 tools**.

Every tool is wrapped with an `audit` middleware (JSONL log at
`app/logs/mcp/YYYY-MM-DD.jsonl`) and a token `budget` middleware that caps
response size and emits a `continuation_token` for large results.

---

## Search — find anything across your workspace

Hybrid retrieval pipeline (BM25 + local embeddings + reranker) running
entirely on your machine. The model receives only the top-k distilled
chunks — not your whole workspace.

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_search_memory` | Hybrid search across notes **and** Jira issues. Returns top-k chunks with paths and scores. Scope selectable: `all` / `notes` / `jira`. | One call to retrieve relevant context from every source — no need to pick where to look. Cuts cloud token spend by shipping only the best chunks. |
| `jarvis_search_notes` | Same pipeline, scoped to knowledge-base notes only (skips Jira). | Focused answers from your own notes when Jira noise would dilute results. |
| `jarvis_search_jira` | Same pipeline, scoped to Jira issues only. | Fast ticket lookup by natural language instead of JQL. |

---

## Notes — read and navigate your Markdown memory

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_note_read` | Reads a single note by workspace-relative path. Returns frontmatter + body, truncated to `max_chars`. | Grounded answers citing the exact note — no hallucinated content. |
| `jarvis_note_list` | Lists notes in a folder, with optional `tag` and `modified_after` filters. Returns paths + titles only. | Cheap directory listing — lets the agent discover what exists before pulling full content. |
| `jarvis_note_outline` | Returns only the headings + frontmatter of a note. | Navigate a long note (design doc, meeting log) without spending tokens on the full body. |

---

## Knowledge graph — reason over entities and relations

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_graph_query` | Queries the knowledge graph around a free-text entity (e.g. `"Adam Nowak"`). Returns neighbors with edge types. Optional `relation_type`, `depth`. | Follow real relationships (person → project → decision) instead of keyword matching. |
| `jarvis_graph_neighbors` | Returns neighbors of a canonical node ID (e.g. `person:adam-nowak`). | Precise expansion once the canonical ID is known — no ambiguity. |
| `jarvis_graph_entity_detail` | Full details of a graph node: aliases, mentions, top related notes/issues. | A complete "who is this / what is this" card the model can ground on. |
| `jarvis_graph_path_between` | Finds the shortest path between two entities (BFS up to `max_depth`). | Explains *how* two things are connected — surfaces hidden links across notes and tickets. |

---

## Jira — structured project context

Operate on your ingested Jira snapshot locally — no calls to Atlassian at query time.

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_jira_describe_issue` | Fetches a Jira issue by key with enriched summary, risk level, and graph neighbors. Optional `include_comments`, `include_neighbors`. | One-shot, model-ready issue brief — no need to chain multiple calls. |
| `jarvis_jira_list_issues` | Filters issues by project / status / assignee / sprint / label. Returns key + title + status + assignee + risk. | Natural-language filtering without writing JQL. |
| `jarvis_jira_blockers_of` | Finds direct and transitive blockers of a given issue. | Immediately see the real chain keeping a ticket stuck. |
| `jarvis_jira_depends_on` | Finds issues that depend on a given issue. | Understand downstream impact before changing scope or priority. |
| `jarvis_jira_sprint_risk` | Risk overview for a sprint: all issues with risk level, ambiguity, blocking chains, assignee bottlenecks. Auto-picks the current sprint when omitted. | Full sprint health in one call — replaces several `list_issues` + search follow-ups. |
| `jarvis_jira_cluster_by_topic` | Groups Jira issues by business area / topic. Returns clusters with `issue_count`, `avg_risk`, `issue_keys`. | Spot hot areas and risk concentrations without manual triage. |

---

## Sessions — learn from your own history

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_session_recent` | Lists recent Jarvis chat sessions with topic + last-message timestamp. | Quick "what was I working on" recap across clients. |
| `jarvis_session_recent_decisions` | Extracts decisions from recent sessions (`"we decided"`, `"let's go with"`, …). Filterable by `topic`. | Durable decision log — avoids re-deciding what was already settled. |
| `jarvis_session_tool_history` | Aggregated tool usage from recent sessions (which tools, how often). | Shows the agent (and user) which patterns actually work in this workspace. |

---

## Workspace & preferences — context about *you*

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_get_preferences` | Returns saved user preferences, optionally filtered by `category` prefix. | The agent adapts to your conventions (tone, formatting, project defaults) on every call. |
| `jarvis_list_specialists` | Lists user-defined specialist personas with their focus areas. | External clients can route questions to the right specialist role you already created in Jarvis. |
| `jarvis_workspace_stats` | Counts and freshness: notes, Jira issues, chunks, graph nodes/edges, last enrichment. | Instant health check — confirms the workspace is indexed before asking questions. |

---

## Pagination

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_continue` | Fetches the next page of a previously truncated tool result. Pass the `continuation_token` returned by the earlier call. | Access full results for large queries without exceeding the per-call token budget. |

---

## Write tools (opt-in)

Registered only when `mcp.allow_writes: true` is set in `app/config.json`.
Disabled by default — the server is read-only out of the box.

| Tool | What it does | What the user gains |
|---|---|---|
| `jarvis_save_preference` | Persists a user preference (`category` + `rule`) Jarvis will recall in every future session. | Teach Jarvis once; every client and session inherits the rule. |
| `jarvis_append_note` | Appends a block of text to an existing note. Never creates new notes (safety rail). | Capture useful AI output into durable memory without leaving the external client. |
| `jarvis_summarize_and_save` | Summarizes arbitrary content and (optionally) saves it to a daily note. | Turn long chats and research dumps into reusable, graph-linked notes. |

---

## Cost classes & budgets

Every tool is tagged with a cost class (`free` / `cheap` / `standard` / `premium`)
and a per-call token cap (see `@enforce_budget(max_tokens=…)` in the source).
Per-session caps are configurable in **Settings → MCP**, so you can let the
agent explore freely while still bounding spend.

## Source

Tool definitions live in [`backend/mcp_server/tools/`](../../../backend/mcp_server/tools/):
`search.py`, `notes.py`, `graph.py`, `jira.py`, `sessions.py`, `meta.py`,
`continuation.py`, `writes.py`.
