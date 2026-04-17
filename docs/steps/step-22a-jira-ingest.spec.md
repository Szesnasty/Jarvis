# Step 22a — Jira XML/CSV Streaming Ingest

> **Goal**: Parse large Jira exports (XML from `jira.com/sr/jira.issueviews`
> or CSV from the issue navigator), write one Markdown file per issue to
> `memory/jira/**`, and populate a new `issues` table in SQLite. Idempotent
> by `issue_key`.

**Status**: ⬜ Not started
**Depends on**: step-04 (memory service), step-19b (embeddings for later)
**Effort**: ~3 days

---

## What this step covers

| Feature | Description |
|---|---|
| `services/jira_ingest.py` | Streaming XML + CSV parsers, upsert by `issue_key` |
| `memory/jira/{PROJECT}/{KEY}.md` | One Markdown per issue, frontmatter-rich |
| `issues` SQLite table | Operational index with all structured fields |
| `issue_links` SQLite table | Raw Jira-reported relations (resolved in 22b into graph edges) |
| `issue_sprints` / `issue_labels` / `issue_components` | Many-to-many join tables |
| `routers/jira.py` | `POST /api/jira/import` (multipart), `GET /api/jira/imports` |
| Tests | Golden XML + CSV fixtures, re-import idempotency |

Out of scope: graph edges (22b), enrichment (22c), retrieval (22f).

---

## File layout

```
backend/
  services/
    jira_ingest.py              # NEW
  routers/
    jira.py                     # NEW
  models/
    database.py                 # MODIFY — add schemas below
  tests/
    fixtures/jira/
      small.xml                 # 5 issues, hand-crafted
      sprint.xml                # 40 issues, 2 sprints, 1 epic
      export.csv
    test_jira_ingest.py         # NEW
```

---

## SQLite schema (additions)

```sql
CREATE TABLE IF NOT EXISTS issues (
    issue_key       TEXT PRIMARY KEY,     -- e.g. "ONB-142"
    project_key     TEXT NOT NULL,        -- "ONB"
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    issue_type      TEXT NOT NULL,        -- Story / Bug / Task / Epic / Sub-task
    status          TEXT NOT NULL,
    status_category TEXT,                 -- "to-do" | "in-progress" | "done"
    priority        TEXT,
    assignee        TEXT,
    reporter        TEXT,
    epic_key        TEXT,                 -- parent epic if any
    parent_key      TEXT,                 -- sub-task parent
    due_date        TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    source_url      TEXT,
    note_path       TEXT NOT NULL,        -- 'memory/jira/ONB/ONB-142.md'
    content_hash    TEXT NOT NULL,        -- sha256 of normalised payload
    imported_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issues_project   ON issues(project_key);
CREATE INDEX IF NOT EXISTS idx_issues_status    ON issues(status_category);
CREATE INDEX IF NOT EXISTS idx_issues_assignee  ON issues(assignee);
CREATE INDEX IF NOT EXISTS idx_issues_updated   ON issues(updated_at);
CREATE INDEX IF NOT EXISTS idx_issues_epic      ON issues(epic_key);

CREATE TABLE IF NOT EXISTS issue_labels (
    issue_key TEXT NOT NULL,
    label     TEXT NOT NULL,
    PRIMARY KEY (issue_key, label),
    FOREIGN KEY (issue_key) REFERENCES issues(issue_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS issue_components (
    issue_key TEXT NOT NULL,
    component TEXT NOT NULL,
    PRIMARY KEY (issue_key, component),
    FOREIGN KEY (issue_key) REFERENCES issues(issue_key) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS issue_sprints (
    issue_key    TEXT NOT NULL,
    sprint_name  TEXT NOT NULL,
    sprint_state TEXT,          -- "active" | "closed" | "future"
    PRIMARY KEY (issue_key, sprint_name),
    FOREIGN KEY (issue_key) REFERENCES issues(issue_key) ON DELETE CASCADE
);

-- Raw Jira-reported links. 22b turns these into typed graph edges.
CREATE TABLE IF NOT EXISTS issue_links (
    source_key TEXT NOT NULL,
    target_key TEXT NOT NULL,
    link_type  TEXT NOT NULL,   -- "blocks" | "is blocked by" | "relates to" | "duplicates" | "clones" | "parent_of" | "in_epic"
    direction  TEXT NOT NULL,   -- "outbound" | "inbound"
    PRIMARY KEY (source_key, target_key, link_type, direction)
);

CREATE INDEX IF NOT EXISTS idx_links_target ON issue_links(target_key);

CREATE TABLE IF NOT EXISTS issue_comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_key   TEXT NOT NULL,
    author      TEXT,
    created_at  TEXT,
    body        TEXT,
    FOREIGN KEY (issue_key) REFERENCES issues(issue_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comments_issue ON issue_comments(issue_key);

-- Import batches (for audit and rollback)
CREATE TABLE IF NOT EXISTS jira_imports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    format          TEXT NOT NULL,   -- "xml" | "csv"
    project_keys    TEXT NOT NULL,   -- JSON array
    issue_count     INTEGER NOT NULL,
    inserted        INTEGER NOT NULL,
    updated         INTEGER NOT NULL,
    skipped         INTEGER NOT NULL,
    bytes_processed INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT NOT NULL
);
```

---

## Markdown layout (per issue)

Path: `memory/jira/{PROJECT_KEY}/{ISSUE_KEY}.md`

```markdown
---
title: "ONB-142 — Session expires during onboarding wizard"
issue_key: ONB-142
project_key: ONB
type: jira_issue
issue_type: Bug
status: In Progress
status_category: in-progress
priority: High
assignee: michal.kowalski
reporter: anna.nowak
epic: ONB-100
sprint: Onboarding Sprint 14
labels: [onboarding, auth, session]
components: [web-auth, onboarding-flow]
created_at: 2026-03-08T10:11:00Z
updated_at: 2026-04-14T16:03:00Z
due_date: 2026-04-21
source_url: https://jira.example.com/browse/ONB-142
tags: [jira, jira/ONB, jira/bug, jira/status/in-progress]
---

# ONB-142 — Session expires during onboarding wizard

## Description

<normalised Jira wiki markup converted to Markdown>

## Acceptance criteria
- …

## Comments

### 2026-03-11 — anna.nowak
…

### 2026-04-14 — michal.kowalski
…

## Links
- blocks: [[ONB-150]]
- is blocked by: [[AUTH-88]]
- relates to: [[ONB-141]]
```

Rules:

- Wiki-links `[[KEY]]` so the existing entity extractor (step-14a) picks them up.
- `tags` include `jira/{PROJECT}`, `jira/{issue_type_lower}`, `jira/status/{category}` to make BM25 filters cheap.
- Body is normalised: Jira markup → Markdown, tables preserved, code fences kept.
- The file is the source of truth; rebuilding the DB re-reads every file.

---

## Parsing rules

### XML (iterparse, streaming)

```python
# Pseudocode — real code in jira_ingest.py
def iter_xml_issues(path: Path) -> Iterator[RawIssue]:
    context = ET.iterparse(path, events=("end",))
    for event, elem in context:
        if elem.tag != "item":
            continue
        yield _parse_item(elem)
        elem.clear()                    # drop from memory
        # also drop siblings to keep root small
        while elem.getprevious() is not None:
            del elem.getparent()[0]
```

- Use `defusedxml.ElementTree.iterparse` (safe against XXE).
- Normalise custom fields via `<customfield id="…" key="com.atlassian.jira.plugin.system.customfieldtypes:sprint">`.
- Sprint values come as `com.atlassian.greenhopper.service.sprint.Sprint@abc[id=…,name=…,state=…]` — parse with a regex, not `eval`.

### CSV

- Use `csv.DictReader`. Auto-detect header row.
- Jira CSV duplicates columns named `Comment`, `Sprint`, `Label` etc. — the std lib only keeps the last. Work around by reading header via `csv.reader`, enumerating `(index, name)` and grouping duplicates into lists.
- Configurable column map in `memory/jira/_config.json` per project, falling back to a built-in default.

### Normalisation

```python
def normalise(raw: RawIssue) -> Issue:
    # Strip Jira wiki markup: {code}, {color}, {quote}, {panel} → Markdown
    # Collapse whitespace
    # UTC-normalise timestamps
    # Compute content_hash over (title, description, status, priority,
    # assignee, labels, components, sorted links) — NOT updated_at,
    # NOT comments. Prevents needless re-enrichment on trivial changes.
```

---

## Idempotent upsert

```
for raw in iter_issues(source):
    issue = normalise(raw)
    hash_ = sha256(issue.canonical_payload())
    existing = await db.fetch_one("SELECT content_hash FROM issues WHERE issue_key = ?", key)
    if existing and existing["content_hash"] == hash_:
        stats.skipped += 1
        continue
    await write_markdown(issue)        # atomic: write to .tmp then rename
    await upsert_issue_row(issue, hash_)
    await replace_m2m(issue)           # labels/components/sprints/links/comments
    stats.inserted_or_updated += 1
    await queue_for_enrichment(issue.issue_key, hash_)   # 22c
```

Atomic file write is required because we re-read Markdown on rebuild.

---

## API

```
POST /api/jira/import
  multipart/form-data: file=<xml|csv>, project_filter=ONB,AUTH
  → 202 { import_id, stream_url: "/api/jira/imports/{id}/stream" }

GET /api/jira/imports
  → [{ id, filename, issue_count, inserted, updated, skipped, started_at, finished_at }]

GET /api/jira/imports/{id}/stream
  → SSE: { type: "progress", processed, total, rate } / { type: "done", stats }

GET /api/jira/issues?status=open&sprint=...&assignee=...&limit=50
  → paginated list for UI (not retrieval; that lives in 22f)
```

Security:
- File size cap (config-driven, default 512 MB).
- MIME/extension whitelist: `application/xml`, `text/xml`, `text/csv`.
- `defusedxml` only — never stdlib ET for user input.
- Path traversal: `issue_key` must match `^[A-Z][A-Z0-9_]+-[0-9]+$` before used in filenames.

---

## Tests

- `test_xml_streaming_memory`: parse a 100 MB synthetic XML, assert peak RSS ≤ 300 MB.
- `test_csv_duplicate_columns`: Jira-style CSV with three `Sprint` columns, all values captured.
- `test_reimport_idempotent`: import the same file twice → `inserted=N, updated=0, skipped=N`.
- `test_field_change_triggers_update`: change status only → `updated=1`, `content_hash` differs.
- `test_markdown_roundtrip`: ingest → delete DB rows → rebuild from MD → identical rows.
- `test_xxe_blocked`: XML with external entity → parser rejects.
- `test_path_traversal_blocked`: crafted `issue_key` with `..` → rejected.

---

## Definition of done

- XML and CSV imports work on a 200 MB real export.
- Re-importing the same export produces zero writes beyond the stats row.
- Every issue has a Markdown file, a row in `issues`, and rows in the m2m tables.
- Deleting `jarvis.db` and re-running a "rebuild index" command recreates
  every row from Markdown alone.
- `docs/.registry.json` updated, `docs/features/jira-ingest.md` authored.
