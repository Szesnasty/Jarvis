# Step 24 — Local MCP Server (Jarvis as a Tool for Other Apps)

> **Goal**: Expose Jarvis's memory, knowledge graph, and Jira intelligence
> as a local **Model Context Protocol** server so external clients (Cursor,
> Claude Desktop, Zed, Continue, custom agents) can query the user's
> personal knowledge without copy-pasting context. This turns Jarvis into
> the "context provider" for the user's whole AI tooling stack.

**Status**: ⬜ Not started
**Depends on**: 04 (memory), 08 (graph), 19c (hybrid retrieval), 22a–f (Jira), feat/privacy-offline-mode (kill-switches)
**Effort**: ~4 days (2.5 backend + 1 frontend + 0.5 integration/eval)

**Mandate**: Expose the **full Jarvis tool surface** so external clients can
exploit every retrieval, graph, and reasoning shortcut Jarvis already has.
Measure success by two numbers — **tokens saved per task** and **answer
quality vs. baseline**. A narrow tool set means clients fall back to raw
dumps (no savings) or wrong answers (no quality). Both kill the value
proposition.

---

## Why this exists

| Pain today | Solution |
|---|---|
| User in Cursor needs Jira context — copies & pastes raw issues, blowing the prompt | Cursor calls `jarvis_jira_describe(KEY)`, gets a 200-token enriched summary |
| User asks Cursor "what's blocking LOGIN-123?" — Cursor has no way to know | `jarvis_jira_blockers_of` returns 3 IDs from the Jarvis graph |
| User has private notes Jarvis already indexed — duplicating into Cursor's project context wastes tokens and goes stale | `jarvis_search_memory` returns top-k reranked chunks on demand |
| External agents re-summarize the same epic in every conversation | `jarvis_jira_sprint_risk` and `jarvis_jira_cluster_by_topic` return cached, pre-computed analyses |
| Each AI tool reinvents its own retrieval | Jarvis becomes the single source of truth for personal knowledge |

**Token economics** (measured baselines, not guesses — verify in 24c eval):

| Workflow | Without MCP | With MCP | Saving |
|---|---|---|---|
| "What's `ONB-142` about and what blocks it?" | 8–15k (raw Jira XML pasted) | 0.5–1.5k (enriched summary + blocker IDs) | ~10× |
| "Find my notes about onboarding rate limits" | N/A — user manually searches Obsidian | 1–3k (top-3 reranked chunks) | priceless |
| "Continue work on the auth refactor" | full file dumps from grep | 2–4k (chunk-aware retrieval + graph neighbors) | 3–5× |
| "Risk overview of the current sprint" | dump 40 issues × 500 tokens = 20k | 1k (`jarvis_jira_sprint_risk` returns ranked summary) | 20× |
| "What did I decide about auth in the last 2 weeks?" | grep + paste session logs (10k+) | 1.5k (`jarvis_recent_decisions` filtered by topic) | 7× |
| "What does the user prefer when writing tests?" | trial-and-error, repeat mistakes | 0.2k (`jarvis_get_preferences` filtered by category) | priceless |

---

## Sub-steps

This work is split into three specs:

| Sub-step | Scope | Effort |
|---|---|---|
| **[24a — MCP Server Backend](step-24a-mcp-server-backend.spec.md)** | New `services/mcp/` module, stdio + SSE transports, 7 tools mapped onto existing services, auth, privacy gate | ~2 days |
| **[24b — MCP Server Frontend Toggle](step-24b-mcp-server-frontend.spec.md)** | Settings → MCP Server section, start/stop toggle next to "Alive" indicator, copyable client snippets | ~0.5 day |
| **[24c — Client Integration & Docs](step-24c-mcp-client-integration.spec.md)** | Reference configs for Cursor / Claude Desktop / Continue, eval harness measuring token savings | ~0.5 day |

---

## Architectural decisions

### 1. Single source of truth — no duplication

Tools are **thin wrappers** over existing services. The full mapping lives
in [step-24a §Tool catalogue](step-24a-mcp-server-backend.spec.md). Six
namespaces, ~18 tools at GA:

| Namespace | Tools | Purpose |
|---|---|---|
| `jarvis_search_*` | `memory`, `notes`, `jira` | Hybrid + scoped retrieval (top-k reranked) |
| `jarvis_note_*` | `read`, `list`, `outline` | Direct note access with smart truncation |
| `jarvis_graph_*` | `query`, `neighbors`, `path`, `entity_detail` | Graph traversal + entity expansion |
| `jarvis_jira_*` | `describe_issue`, `list_issues`, `blockers_of`, `depends_on`, `sprint_risk`, `cluster_by_topic` | Pre-computed, enriched Jira intelligence |
| `jarvis_session_*` | `recent`, `recent_decisions`, `tool_history` | What the user worked on / decided / accessed lately |
| `jarvis_meta_*` | `get_preferences`, `list_specialists`, `workspace_stats` | Self-description so agents can route smartly |

Zero business logic in `services/mcp/`. If a tool grows logic, it belongs
in the existing service module, not in the MCP layer.

### 2. Two transports, one server

- **stdio** — default for desktop clients (Claude Desktop, Cursor); zero
  config, one process per client, lifetime managed by the client.
- **SSE over HTTP** on `127.0.0.1:8765` — for clients that don't spawn
  processes (web tools, custom agents); started/stopped from Jarvis UI;
  protected by a per-workspace token.

The same handler set serves both transports — choice is just which
listener wraps it.

### 3. Privacy is non-negotiable

The kill-switches from `feat/privacy-offline-mode` apply transparently:

- MCP tools that are pure-local (memory, graph, Jira) work even in
  **offline mode** — they touch no external network.
- MCP tools that would call external services (none in MVP, but e.g. a
  future `jarvis_web_search` proxy) go through `services.privacy` like
  every other call — they fail with the same `PrivacyBlockedError`.
- The MCP server itself binds to `127.0.0.1` only. There is no flag to
  expose it on `0.0.0.0`. If a user wants remote access, they can use
  SSH port forwarding — we do not provide a footgun.

### 4. Auth even on localhost

Localhost is **not** a security boundary on a multi-user machine, and
malicious processes (browser tabs via DNS rebinding, rogue Electron apps)
can hit `127.0.0.1`. So:

- **stdio**: trust process boundary (whoever spawned us is who we serve).
- **SSE**: require `Authorization: Bearer <token>` header. Token is
  generated per workspace, displayed once in the UI, stored in
  `app/mcp_token`, regeneratable, never logged.

### 5. Read-only first, opt-in write

MVP ships **read-only** by default. Three write tools are implemented
but **gated behind a per-workspace flag** `mcp.allow_writes` (default
`false`):

- `jarvis_save_preference` — most-requested write; cheap to undo.
- `jarvis_append_note` — diff-friendly; safe.
- `jarvis_summarize_and_save` — append a summary to a daily note.

When writes are disabled, those tools are **not advertised** in
`tools/list` so agents don't even see them. Hard `jarvis_create_note`,
`jarvis_delete_note`, plan mutations remain Step 25.

Reasoning:

- Write tools without UI confirmation could pollute notes silently.
- But preference writing is what makes Jarvis *learn* across tools — if
  the user tells Cursor "I prefer pnpm", Jarvis should remember it.
- The opt-in flag puts the user in control without forcing a UI confirm
  loop on every write.

### 6. Observability

Every MCP call is logged to `app/logs/mcp.jsonl` with:

```json
{
  "ts": "2026-04-18T12:00:00Z",
  "transport": "stdio",
  "client": "cursor-1.42",
  "tool": "jarvis_jira_describe_issue",
  "args_hash": "ab12…",
  "duration_ms": 87,
  "result_bytes": 1240,
  "error": null
}
```

Args are hashed (not stored) to preserve privacy while still allowing
"how often is this tool called" analytics. The Jarvis Settings page
exposes a small read-out: "MCP calls today: 142 · last call 12s ago".

### 7. SQLite concurrency

The MCP server reads the same SQLite DB as FastAPI. Two safeguards:

- **WAL mode** (verify it's already enabled in `models/database.py`; if
  not, this step turns it on).
- Read tools open connections **read-only** via
  `sqlite3.connect(uri=True, ...)` with `?mode=ro` in the URI.
- Write tools (when `mcp.allow_writes=true`) reuse the existing service
  functions (`memory_service.append_note`, `preference_service.save_preference`)
  — no parallel write paths, so all of FastAPI's safety nets apply.

### 8. Cost & quality budgets per tool

Every tool declares a `cost_class` and a `max_output_tokens` budget,
enforced server-side:

| Cost class | Max output tokens | Examples |
|---|---|---|
| `cheap` (DB query, < 50ms) | 1,000 | `list_issues`, `get_preferences`, `query_graph` (depth=1) |
| `medium` (retrieval + rerank, < 500ms) | 4,000 | `search_memory`, `describe_issue`, `recent_decisions` |
| `heavy` (LLM-touching, only with local Ollama) | 8,000 | `summarize_and_save`, `cluster_by_topic` |

If the natural output exceeds the budget, the tool truncates with a
`continuation_token` so the agent can ask for more — but pays for the
decision rather than getting the dump for free. This is **the** mechanism
that actually reduces tokens; tool *count* alone won't.

---

## Killer feature — `jarvis_session_url`

Every tool response includes a `meta.jarvis_session_url` field:

```json
{
  "issue_key": "ONB-142",
  "summary": "Session expires during the onboarding wizard …",
  "blockers": ["AUTH-88"],
  "meta": {
    "jarvis_session_url": "http://127.0.0.1:3000/jira/ONB-142?via=mcp",
    "retrieved_at": "2026-04-18T12:00:00Z",
    "from_cache": false
  }
}
```

The user clicks the URL → opens Jarvis with the issue + graph context
preloaded. **No other MCP server does this.** It turns Jarvis from a
"context API" into a "context dashboard you trust" — every answer in
Cursor is one click away from the source of truth.

---

## Out of scope (deferred)

- ❌ Hard mutations (`create_note`, `delete_note`, `update_plan`) — Step 25
- ❌ Streaming tool output (the MCP spec supports it; our tools all return in <500ms)
- ❌ MCP **resources** and **prompts** (only `tools` in MVP — they cover the use case)
- ❌ Multi-workspace (one MCP server == one workspace; users with multiple
  workspaces run multiple Jarvis instances on different ports)
- ❌ Cloud-hosted MCP gateway (defeats the local-first promise)
- ❌ Rate limiting (premature — local clients, single user)

---

## Acceptance criteria

- [ ] All three sub-step specs (24a, 24b, 24c) are implemented and
      their individual DoD checklists pass.
- [ ] At least **15 read tools** advertised in `tools/list`, covering
      memory, graph, Jira, sessions, and metadata.
- [ ] A fresh user can: install Jarvis → toggle MCP server on → paste
      one config snippet into Cursor → ask Cursor about a Jira issue →
      see a Jarvis-powered answer. End-to-end ≤ 5 minutes.
- [ ] In offline mode, MCP server starts and serves every local tool;
      no tool call sends data outside the machine.
- [ ] Eval (24c) shows on the 8-task benchmark: median **≥ 5× token
      reduction** and **answer quality ≥ baseline** (judged by Claude
      against ground truth, blind).
- [ ] No regression in existing test suites.

---

## References

- [MCP specification](https://modelcontextprotocol.io/specification)
- [Anthropic MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [feat/privacy-offline-mode](../../backend/services/privacy.py) — kill-switch source of truth
- [Step 22f — Jira Retrieval](step-22f-jira-retrieval.spec.md) — backend functions reused by MCP
- [Step 19c — Hybrid Retrieval](step-19c-hybrid-retrieval-graph-semantic.md) — `hybrid_search` reused by MCP
