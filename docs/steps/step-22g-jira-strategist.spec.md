# Step 22g — Jira Strategist Specialist + Tools + Duel Presets

> **Goal**: Wrap everything built in 22a–f into a specialist profile the
> user can invoke from chat: *Jira Strategist*. Add a small set of
> deterministic tools so answers are grounded in the index, not in the
> model's guesses. Provide Duel Mode presets that make decision work
> around tickets fun and sharp.

**Status**: ⬜ Not started
**Depends on**: 22a–f, step-09 (specialists), step-16a/b (duel)
**Effort**: ~2 days

---

## Specialist profile

Stored at `Jarvis/agents/jira-strategist.json` on first run, managed
through the existing Specialist Wizard. Key fields:

```json
{
  "id": "jira-strategist",
  "name": "Jira Strategist",
  "role": "Helps analyse tasks, clusters, blockers, sprint risk and owner load across the Jira export and the rest of the workspace.",
  "knowledge_scope": {
    "subject_types": ["jira_issue", "jira_epic", "decision", "note"],
    "folders_allow": ["memory/jira/**", "memory/decisions/**", "memory/projects/**", "memory/people/**"]
  },
  "style": {
    "tone": "direct, operational",
    "length": "short, bulleted when listing issues",
    "citation": "always include issue keys in brackets"
  },
  "rules": [
    "Never invent issue keys — only cite keys that appear in context.",
    "When listing blockers, use hard 'blocks' / 'depends_on' edges first, then soft 'likely_dependency_on' flagged as '(likely)'.",
    "When a task is unclear, say so explicitly and cite the enrichment ambiguity level."
  ],
  "tools_allow": [
    "search_notes", "open_note",
    "jira_list_issues", "jira_describe_issue",
    "jira_blockers_of", "jira_depends_on",
    "jira_sprint_risk", "jira_cluster_by_topic",
    "write_note"
  ]
}
```

The wizard exposes a "Use sample data" toggle that pre-seeds this
profile when a Jira import is detected.

---

## Tools (new)

All tools are deterministic wrappers over the SQLite index and graph.
They return compact JSON suitable for the LLM. No free-text from these
tools — they surface the indexed truth.

### `jira_list_issues`

```
input: { facets?: FacetFilter, limit?: int ≤ 50, sort?: "updated" | "risk" | "priority" }
output: [
  { key, title, status, priority, assignee, sprint, risk, area, summary }
]
```

### `jira_describe_issue`

```
input: { key }
output: {
  key, title, status, priority, assignee, reporter, sprint, epic,
  enrichment: { summary, work_type, business_area, execution_type,
                risk_level, ambiguity_level, hidden_concerns,
                actionable_next_step },
  hard_links: { blocks: [...], depends_on: [...], duplicate_of: [...],
                in_epic, parent_of: [...] },
  soft_links: { same_topic_as: [{key, confidence}], likely_dependency_on: [...] },
  related_notes: [{ path, title, confidence }],
  related_decisions: [{ path, title, confidence }]
}
```

### `jira_blockers_of`

```
input: { key }
output: {
  direct_blockers: [key, ...],     # hard 'depends_on'
  transitive_blockers: [key, ...], # BFS over 'depends_on', max_depth=3
  likely_blockers: [{key, confidence}, ...]   # 'likely_dependency_on'
}
```

### `jira_depends_on`

Mirror of `jira_blockers_of`, following `blocks`.

### `jira_sprint_risk`

```
input: { sprint_name? }   # defaults to active sprint
output: {
  sprint_name,
  issues: [{ key, title, risk, ambiguity, status, assignee, blocking_chain_length }],
  top_risks: [key, ...],           # risk_level="high"
  top_unclear: [key, ...],          # ambiguity_level="unclear"
  bottlenecks: [{ assignee, open_count, high_risk_count }]
}
```

### `jira_cluster_by_topic`

```
input: { root_keys?: [key], top_k?: int }
output: [
  { topic_label, issue_keys: [...], business_area, avg_risk }
]
```

Topic labelling: take the most frequent canonical entity label in the
cluster's chunks; fallback to the most frequent enrichment keyword.

---

## Duel Mode presets (declared in this step)

Surface the following presets in the existing Duel setup UI:

| Preset                           | Side A               | Side B               | Prompt focus                            |
|----------------------------------|----------------------|----------------------|-----------------------------------------|
| Delivery Planner vs Risk Analyst | ship sooner          | protect stability    | sprint contents, blockers                |
| Product Strategist vs Tech Lead  | user outcomes        | technical debt       | epic scoping, trade-offs                 |
| Pragmatist vs Refactor Specialist| get it done          | clean it up          | ticket rewrites, incremental vs big bang |
| Growth PM vs Stability Guardian  | new users            | current users        | prioritisation across business areas     |

Each preset is a JSON in `memory/duel_presets/*.json`; they are mounted
into the existing Duel flow, not hardcoded.

On duel completion, the orchestrator:

1. Writes a verdict note into `memory/plans/duel-{date}-{topic-slug}.md`.
2. Emits derived graph edges of type `duel_recommendation` from the
   verdict note to each referenced issue (`source="derived"`, weight =
   vote margin).
3. Optionally queues the referenced issues for a targeted re-enrichment
   (prompt_version bumped? no — we reuse the existing one).

---

## Tests

- `test_tool_list_issues_facets`: all facet combinations produce valid SQL.
- `test_tool_describe_issue_missing`: unknown key → 404-style error JSON.
- `test_tool_blockers_transitive_depth_cap`: BFS respects `max_depth=3`.
- `test_specialist_scope_enforced`: a prompt asking for notes outside
  `knowledge_scope.folders_allow` is denied by `memory_service`.
- `test_duel_verdict_saves_note_and_edges`: verdict note exists, edges
  with `duel_recommendation` type emitted.

---

## Definition of done

- User can say *"use the Jira Strategist"* and chat with it.
- Tool calls land in the chat trace and return the JSON above.
- Running a duel on *"what should go into the next sprint?"* produces a
  saved plan and graph annotations.
- `docs/features/jira-strategist.md` authored.
