# Jira Graph Projection

**Step**: 22b
**Status**: Current
**Last updated**: 2026-04-17

## Summary

Projects imported Jira issues, epics, sprints, projects, people, components, and labels into the knowledge graph as first-class typed nodes with weighted edges. This transforms the graph from a notes-only structure to a work-aware knowledge layer.

## How It Works

### Node Types

| `node.type` | ID pattern | Source |
|---|---|---|
| `jira_issue` | `issue:{KEY}` | Every issue from `issues` table |
| `jira_epic` | `epic:{KEY}` | Issues where `issue_type = "Epic"` (shadow node) |
| `jira_sprint` | `sprint:{slug}` | `issue_sprints` table |
| `jira_project` | `project:{KEY}` | Distinct `project_key` values |
| `jira_person` | `person:{name}` | Assignees, reporters, comment authors |
| `jira_component` | `component:{slug}` | `issue_components` table |
| `jira_label` | `label:{slug}` | `issue_labels` table |

Epics exist as both `jira_issue` and `jira_epic` nodes, joined by an `is_epic_shadow` edge (weight 1.0).

### Edge Types

All edges carry `origin="jira"` and are regenerated on every import:

| Edge type | From → To | Weight | Source |
|---|---|---|---|
| `blocks` | issue → issue | 1.0 | outbound "blocks" links |
| `depends_on` | issue → issue | 1.0 | "is blocked by" links |
| `duplicate_of` | issue → issue | 1.0 | "duplicates" links |
| `relates_to` | issue → issue | 0.9 | "relates to" links |
| `in_epic` | issue → epic | 1.0 | `issues.epic_key` |
| `parent_of` | parent → child | 1.0 | `issues.parent_key` |
| `in_sprint` | issue → sprint | 1.0 | `issue_sprints` |
| `in_project` | issue → project | 1.0 | `issues.project_key` |
| `assigned_to` | issue → person | 1.0 | `issues.assignee` |
| `reported_by` | issue → person | 0.9 | `issues.reporter` |
| `has_component` | issue → component | 0.9 | `issue_components` |
| `has_label` | issue → label | 0.8 | `issue_labels` |
| `commented_by` | issue → person | 0.7 | `issue_comments` |

### Idempotency

The projection is fully idempotent: it removes all `origin="jira"` edges first, then re-emits them from the current SQLite state. Running it twice produces the same graph.

### Integration Points

1. **After import**: `jira_ingest.run_import()` calls `project_jira()` automatically when issues are inserted or updated.
2. **During rebuild**: `builder.rebuild_graph()` includes a Jira projection pass (Pass 8) that reads from SQLite.
3. **Builder skip**: Jira markdown files (`type: jira_issue` in frontmatter) are skipped during note parsing (Pass 1) to avoid duplicate `note:` nodes.

### Edge.origin Field

A new `origin: str` field was added to the `Edge` dataclass (default `"generic"`). This enables provenance tracking — edges from Jira have `origin="jira"`, future derived edges will use `origin="derived"`. The field is serialized to `graph.json` (omitted when `"generic"` for compactness) and participates in equality checks.

## Key Files

| File | Purpose |
|---|---|
| [jira_projection.py](../../backend/services/graph_service/jira_projection.py) | Main projection logic: reads SQLite, emits graph nodes/edges |
| [models.py](../../backend/services/graph_service/models.py) | `Edge.origin` field, `Graph.remove_edges_by_origin()` |
| [builder.py](../../backend/services/graph_service/builder.py) | Jira projection pass + jira note skip in Pass 1 |
| [jira_ingest.py](../../backend/services/jira_ingest.py) | Auto-projection call after successful import |
| [__init__.py](../../backend/services/graph_service/__init__.py) | Re-exports `project_jira`, `ProjectionStats` |

## API / Interface

```python
from services.graph_service.jira_projection import project_jira, ProjectionStats

stats: ProjectionStats = project_jira(workspace_path, graph)
# stats.issues, stats.edges_added, stats.edges_removed, etc.
```

No new HTTP endpoints — projection runs automatically.

## Gotchas

- **Edge equality**: `origin` participates in `Edge.__eq__` (frozen dataclass). Two edges with same source/target/type but different origin are distinct.
- **Person resolution**: Falls back to raw display name if entity canonicalization is unavailable.
- **Sprint state**: Stored in `Node.folder` field as lightweight metadata (no schema change).
- **Stub nodes**: If an issue references a target that wasn't imported (e.g., a cross-project link), a stub `jira_issue` node is created with just the key as label.
