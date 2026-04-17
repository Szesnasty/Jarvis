# Step 22b — Jira Entities & Explicit (Hard) Graph Edges

> **Goal**: Teach the graph that Jira issues, epics, sprints, projects and
> Jira users are distinct node types, and project the Jira-reported
> relations from `issue_links` into typed graph edges with high weight.

**Status**: ⬜ Not started
**Depends on**: 22a, step-08 (graph model), step-14a (entity extraction)
**Effort**: ~2 days

---

## New node types

| `node.type`      | Source             | ID pattern                        | Label                       |
|------------------|--------------------|-----------------------------------|-----------------------------|
| `jira_issue`    | `issues` table     | `issue:{KEY}`                     | `"{KEY} — {title}"`         |
| `jira_epic`     | `issues` table where `issue_type="Epic"` | `epic:{KEY}` | `"{KEY} — {title}"`   |
| `jira_sprint`   | `issue_sprints`    | `sprint:{slug(name)}`             | `"{sprint_name}"`           |
| `jira_project`  | distinct `project_key` | `project:{KEY}`               | `{KEY}`                     |
| `jira_person`   | assignees, reporters, comment authors | `person:{canonical}` | `{display_name}`   |
| `jira_component`| `issue_components` | `component:{slug}`                | `{component}`               |
| `jira_label`    | `issue_labels`     | `label:{slug}`                    | `{label}`                   |

Existing person canonicalisation (step-20d) is reused: Jira display names
and email prefixes feed the alias table so `michal.kowalski` and
`Michał Kowalski` end up on the same node.

Epics are materialised twice: once as a `jira_issue` node (so they
participate in issue retrieval) and once as a `jira_epic` node (so we can
say "everything in epic X"). The two are joined with an `is_epic_shadow`
edge (weight 1.0, type ignored during retrieval to avoid double-count).

---

## Hard edge catalogue

All edges below are emitted with `source="jira"`, `weight ∈ [0.9, 1.0]`,
and are regenerated on every import (not accumulated).

| Edge type             | From            | To              | Built from                              | Weight |
|-----------------------|-----------------|-----------------|-----------------------------------------|--------|
| `blocks`             | `jira_issue`   | `jira_issue`   | `issue_links` where `link_type="blocks"` or inverse inbound | 1.0 |
| `depends_on`         | `jira_issue`   | `jira_issue`   | `"is blocked by"` inbound              | 1.0 |
| `duplicate_of`       | `jira_issue`   | `jira_issue`   | `"duplicates"`                          | 1.0 |
| `relates_to`         | `jira_issue`   | `jira_issue`   | `"relates to"`                          | 0.9 |
| `in_epic`            | `jira_issue`   | `jira_epic`    | `issues.epic_key`                       | 1.0 |
| `parent_of`          | `jira_issue`   | `jira_issue`   | `issues.parent_key`                     | 1.0 |
| `in_sprint`          | `jira_issue`   | `jira_sprint`  | `issue_sprints`                         | 1.0 |
| `in_project`         | `jira_issue`   | `jira_project` | `issues.project_key`                    | 1.0 |
| `assigned_to`        | `jira_issue`   | `jira_person`  | `issues.assignee`                       | 1.0 |
| `reported_by`        | `jira_issue`   | `jira_person`  | `issues.reporter`                       | 0.9 |
| `has_component`      | `jira_issue`   | `jira_component` | `issue_components`                    | 0.9 |
| `has_label`          | `jira_issue`   | `jira_label`   | `issue_labels`                          | 0.8 |
| `commented_by`       | `jira_issue`   | `jira_person`  | `issue_comments` (dedup)                | 0.7 |

Soft / derived edges (`same_topic_as`, `likely_dependency_on`, …) live in
step 22d and always carry `source="derived"`.

---

## Implementation

### 1. `services/graph_service/jira_projection.py` (new)

```python
async def project_jira(workspace_path: Path, graph: Graph) -> ProjectionStats:
    """Idempotently project the Jira SQLite tables into the graph.

    Removes every edge where source='jira' and rebuilds the set.
    Re-uses existing nodes and respects entity canonicalisation.
    """
```

Called at the end of `jira_ingest.run()` and from the existing "rebuild
graph" path.

### 2. Graph model changes (`services/graph_service/models.py`)

Add a `source: str = "generic"` field on `Edge`. Migration is a no-op for
existing edges (default value). Add:

```python
def remove_edges_where_source(self, source: str) -> int: ...
```

This keeps Jira re-imports clean: wipe `source="jira"` edges, re-emit.

### 3. Entity extraction bridge

The existing extractor (step-14a) already produces wiki-links. For Jira
Markdown files:

- Wiki-link `[[ONB-150]]` → resolve to node `issue:ONB-150` if it exists,
  else to a lightweight `jira_issue` stub node with `label=KEY` only.
- Mentions of `@michal.kowalski` in comments → `jira_person:{canonical}`
  via the alias table.

The extractor must learn `jira_issue` and `jira_epic` as known node
types so it stops emitting generic `note` nodes for Jira Markdown files.
Add an explicit short-circuit: if `frontmatter.type == "jira_issue"`, skip
note-node creation and attach wiki-links to the `jira_issue` node
directly.

### 4. Sprint / project inference

Sprints and projects are derived, not carried in XML as nodes. When two
issues reference the same sprint name, they converge on one sprint node.
Sprint state (`active` / `closed` / `future`) is stored on the node as
metadata for retrieval filters in 22f.

---

## Tests

- `test_projection_is_idempotent`: run twice → same edge count, same edges.
- `test_blocks_roundtrip`: ONB-142 blocks ONB-150 → graph has `blocks`
  edge and reverse `depends_on` edge on the inverse side.
- `test_epic_shadow`: epic issue present as both `jira_issue` and
  `jira_epic` with `is_epic_shadow` link.
- `test_sprint_node_merges_across_issues`: two issues in
  `"Onboarding Sprint 14"` → one sprint node, two `in_sprint` edges.
- `test_source_tagging`: every new edge has `source="jira"`; removing
  `source="jira"` and re-projecting yields identical result.
- `test_person_canonicalisation`: `michal.kowalski` and
  `Michał Kowalski` collapse into one person node.

---

## Definition of done

- After import, `GET /api/graph` returns Jira nodes with correct types.
- Navigating to a sprint node returns every issue in the sprint.
- Re-importing the same export does not create duplicate edges.
- Deleting and rebuilding the graph reproduces the exact same topology.
- Docs updated: `docs/features/jira-graph.md`.
