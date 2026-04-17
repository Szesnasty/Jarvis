"""Jira XML/CSV ingest — streaming parsers, Markdown emission, SQLite upsert.

Step 22a implementation. Contract:

- Source of truth is `memory/jira/{PROJECT}/{KEY}.md`.
- SQLite `issues` table + m2m tables are a rebuildable index.
- Idempotent by (issue_key, content_hash): unchanged issues are a no-op.
- Streaming XML via defusedxml.ElementTree.iterparse (safe against XXE).
- Streaming CSV via csv.reader with manual duplicate-column handling.
- Atomic Markdown writes: write to `.tmp`, then `os.replace`.

Not covered here: graph projection (22b), enrichment (22c), retrieval (22f).
"""

import csv
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple

import aiosqlite
from defusedxml import ElementTree as DET

from config import get_settings
from models.database import init_database
from utils.markdown import add_frontmatter

logger = logging.getLogger(__name__)


class JiraImportError(Exception):
    pass


# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────

ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,15}-[0-9]{1,9}$")
ISSUE_KEY_EXTRACT_RE = re.compile(r"\b([A-Z][A-Z0-9_]{1,15}-[0-9]{1,9})\b")

# Jira custom field IDs encountered in XML exports.
_CF_SPRINT = "com.atlassian.jira.plugin.system.customfieldtypes:sprint"
_CF_EPIC_LINK = "com.pyxis.greenhopper.jira:gh-epic-link"

# Sprint value format:
# com.atlassian.greenhopper.service.sprint.Sprint@abc123[id=5,rapidViewId=2,state=ACTIVE,name=Sprint 14,...]
_SPRINT_RE = re.compile(
    r"Sprint@[0-9a-f]+\[(?P<attrs>[^\]]*)\]|Sprint\[(?P<attrs2>[^\]]*)\]"
)

_STATUS_CATEGORY_MAP = {
    "to do": "to-do",
    "open": "to-do",
    "reopened": "to-do",
    "new": "to-do",
    "backlog": "to-do",
    "in progress": "in-progress",
    "in review": "in-progress",
    "code review": "in-progress",
    "qa": "in-progress",
    "testing": "in-progress",
    "done": "done",
    "closed": "done",
    "resolved": "done",
    "completed": "done",
}

# Inbound CSV link-type columns Jira emits.
_CSV_LINK_COLS = {
    "Inward issue link (Blocks)": "is blocked by",
    "Outward issue link (Blocks)": "blocks",
    "Inward issue link (Duplicate)": "is duplicated by",
    "Outward issue link (Duplicate)": "duplicates",
    "Inward issue link (Relates)": "relates to",
    "Outward issue link (Relates)": "relates to",
    "Inward issue link (Cloners)": "is cloned by",
    "Outward issue link (Cloners)": "clones",
}


# ────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────


@dataclass
class Sprint:
    name: str
    state: Optional[str] = None


@dataclass
class Link:
    target_key: str
    link_type: str
    direction: str  # "outbound" | "inbound"


@dataclass
class Comment:
    author: Optional[str]
    created_at: Optional[str]
    body: str


@dataclass
class Issue:
    """Normalised issue ready for persistence."""

    issue_key: str
    project_key: str
    title: str
    description: str = ""
    issue_type: str = "Task"
    status: str = ""
    status_category: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    reporter: Optional[str] = None
    epic_key: Optional[str] = None
    parent_key: Optional[str] = None
    due_date: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    source_url: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    sprints: List[Sprint] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)

    @property
    def note_path(self) -> str:
        return f"memory/jira/{self.project_key}/{self.issue_key}.md"

    def canonical_payload(self) -> str:
        """Stable string used for content_hash.

        Deliberately excludes `updated_at`, `imported_at` and comments to
        avoid re-enrichment on trivial changes (Jira bumps `updated` on
        every view in some configs).
        """
        payload = {
            "issue_key": self.issue_key,
            "title": self.title,
            "description": self.description,
            "issue_type": self.issue_type,
            "status": self.status,
            "priority": self.priority or "",
            "assignee": self.assignee or "",
            "reporter": self.reporter or "",
            "epic_key": self.epic_key or "",
            "parent_key": self.parent_key or "",
            "due_date": self.due_date or "",
            "labels": sorted(self.labels),
            "components": sorted(self.components),
            "sprints": sorted(s.name for s in self.sprints),
            "links": sorted(
                f"{l.direction}|{l.link_type}|{l.target_key}" for l in self.links
            ),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_payload().encode("utf-8")).hexdigest()


@dataclass
class ImportStats:
    issue_count: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    bytes_processed: int = 0
    project_keys: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _sanitize_for_log(value: Any) -> str:
    return str(value).replace("\r", "").replace("\n", "")


def _validate_issue_key(key: str) -> str:
    """Raise if the key can't be safely used in a filesystem path."""
    if not isinstance(key, str) or not ISSUE_KEY_RE.match(key):
        raise JiraImportError(f"Invalid issue key: {_sanitize_for_log(key)!r}")
    return key


def _project_from_key(key: str) -> str:
    return key.split("-", 1)[0]


def _normalise_ws(text: Optional[str]) -> str:
    if not text:
        return ""
    # Collapse whitespace but preserve paragraph breaks.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _jira_markup_to_markdown(text: str) -> str:
    """Minimal conversion of common Jira wiki markup to Markdown.

    Deliberately narrow: we only handle the most frequent patterns and
    leave anything else alone. Full conversion is a follow-up step.
    """
    if not text:
        return ""
    s = text
    # Code blocks: {code:lang}...{code} → ```lang\n...\n```
    s = re.sub(
        r"\{code(?::([a-zA-Z0-9_+-]+))?\}(.*?)\{code\}",
        lambda m: f"```{m.group(1) or ''}\n{m.group(2).strip()}\n```",
        s,
        flags=re.DOTALL,
    )
    # Quote blocks: {quote}...{quote} → > ...
    s = re.sub(
        r"\{quote\}(.*?)\{quote\}",
        lambda m: "\n".join("> " + line for line in m.group(1).strip().splitlines()),
        s,
        flags=re.DOTALL,
    )
    # Strip panels: {panel:...}...{panel}
    s = re.sub(
        r"\{panel(?::[^}]*)?\}(.*?)\{panel\}",
        lambda m: m.group(1).strip(),
        s,
        flags=re.DOTALL,
    )
    # Colour: {color:red}text{color} → text
    s = re.sub(r"\{color:[^}]*\}(.*?)\{color\}", r"\1", s, flags=re.DOTALL)
    # Headings: h1. Foo → # Foo
    s = re.sub(
        r"^h([1-6])\.\s*(.+)$",
        lambda m: ("#" * int(m.group(1))) + " " + m.group(2),
        s,
        flags=re.MULTILINE,
    )
    # Bold: *text* → **text** (only when not already ** **)
    s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"**\1**", s)
    return _normalise_ws(s)


def _status_category(status: str) -> Optional[str]:
    if not status:
        return None
    return _STATUS_CATEGORY_MAP.get(status.strip().lower())


def _parse_iso_timestamp(raw: Optional[str]) -> str:
    """Parse Jira timestamps to a UTC ISO8601 string. Empty on failure."""
    if not raw:
        return ""
    raw = raw.strip()
    # Jira XML: "Sun, 8 Mar 2026 10:11:00 +0000"
    # Jira CSV: "08/Mar/26 10:11 AM" or ISO
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%b/%y %I:%M %p",
        "%d/%b/%Y %I:%M %p",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    logger.debug("Could not parse timestamp: %s", _sanitize_for_log(raw))
    return raw  # keep raw; caller can inspect


def _parse_sprint_string(raw: str) -> Optional[Sprint]:
    """Parse the `Sprint@hash[id=..,name=..,state=..]` form."""
    if not raw:
        return None
    m = _SPRINT_RE.search(raw)
    if not m:
        return None
    attrs_str = m.group("attrs") or m.group("attrs2") or ""
    attrs: Dict[str, str] = {}
    # attrs look like: id=5,rapidViewId=2,state=ACTIVE,name=Sprint 14,goal=,...
    # Names can contain commas/equals — this naive split handles the common case.
    for part in attrs_str.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        attrs[k.strip()] = v.strip()
    name = attrs.get("name")
    if not name:
        return None
    state = attrs.get("state")
    if state:
        state = state.strip().lower()
        if state == "active":
            state = "active"
        elif state == "closed":
            state = "closed"
        elif state == "future":
            state = "future"
    return Sprint(name=name, state=state)


# ────────────────────────────────────────────────────────────────────
# XML parser
# ────────────────────────────────────────────────────────────────────


def iter_xml_issues(path: Path) -> Iterator[Issue]:
    """Stream-parse Jira XML export. Safe against XXE via defusedxml."""
    # forbid_dtd=True blocks DTD entirely — Jira exports do not use DTDs.
    parser = DET.iterparse(str(path), events=("end",), forbid_dtd=True)
    for _event, elem in parser:
        if elem.tag != "item":
            continue
        try:
            issue = _parse_xml_item(elem)
        except JiraImportError as exc:
            logger.warning("Skipping invalid issue: %s", exc)
            elem.clear()
            continue
        yield issue
        elem.clear()


def _xml_text(elem, tag: str) -> str:
    node = elem.find(tag)
    if node is None or node.text is None:
        return ""
    return node.text


def _parse_xml_item(elem) -> Issue:
    key = _xml_text(elem, "key").strip()
    if not key:
        raise JiraImportError("Item has no <key>")
    _validate_issue_key(key)

    project_key = _project_from_key(key)
    # Override project_key from explicit <project key="..."> if present.
    project_node = elem.find("project")
    if project_node is not None and project_node.get("key"):
        project_key = project_node.get("key")

    # Detect epic link / parent from customfields and subtask parent.
    epic_key: Optional[str] = None
    parent_key: Optional[str] = None
    sprints: List[Sprint] = []

    for cf in elem.findall("customfields/customfield"):
        cf_id = cf.get("id", "")
        key_attr = cf.get("key", "")
        values: List[str] = []
        for v in cf.findall("customfieldvalues/customfieldvalue"):
            if v.text:
                values.append(v.text)
        if key_attr == _CF_EPIC_LINK or cf_id.endswith(":gh-epic-link"):
            for val in values:
                val = val.strip()
                if ISSUE_KEY_RE.match(val):
                    epic_key = val
                    break
        elif key_attr == _CF_SPRINT or "sprint" in cf_id.lower():
            for val in values:
                sprint = _parse_sprint_string(val)
                if sprint:
                    sprints.append(sprint)

    # Parent sub-task link.
    parent_node = elem.find("parent")
    if parent_node is not None and parent_node.text:
        candidate = parent_node.text.strip()
        if ISSUE_KEY_RE.match(candidate):
            parent_key = candidate

    # Labels & components.
    labels = [
        (l.text or "").strip()
        for l in elem.findall("labels/label")
        if l.text and l.text.strip()
    ]
    components = [
        (c.text or "").strip()
        for c in elem.findall("component")
        if c.text and c.text.strip()
    ]

    # Links.
    links: List[Link] = []
    for lt in elem.findall("issuelinks/issuelinktype"):
        name = (lt.findtext("name") or "").strip().lower()
        for inward in lt.findall("inwardlinks"):
            desc = (inward.get("description") or name or "relates to").lower()
            for issuelink in inward.findall("issuelink/issuekey"):
                target = (issuelink.text or "").strip()
                if target and ISSUE_KEY_RE.match(target):
                    links.append(Link(target, desc, "inbound"))
        for outward in lt.findall("outwardlinks"):
            desc = (outward.get("description") or name or "relates to").lower()
            for issuelink in outward.findall("issuelink/issuekey"):
                target = (issuelink.text or "").strip()
                if target and ISSUE_KEY_RE.match(target):
                    links.append(Link(target, desc, "outbound"))

    # Comments.
    comments: List[Comment] = []
    for c in elem.findall("comments/comment"):
        body = (c.text or "").strip()
        if not body:
            continue
        comments.append(
            Comment(
                author=c.get("author"),
                created_at=_parse_iso_timestamp(c.get("created")),
                body=_jira_markup_to_markdown(body),
            )
        )

    status = _xml_text(elem, "status").strip()
    issue_type = _xml_text(elem, "type").strip() or "Task"

    source_url = _xml_text(elem, "link").strip() or None

    return Issue(
        issue_key=key,
        project_key=project_key,
        title=_normalise_ws(_xml_text(elem, "summary")),
        description=_jira_markup_to_markdown(_xml_text(elem, "description")),
        issue_type=issue_type,
        status=status,
        status_category=_status_category(status),
        priority=_normalise_ws(_xml_text(elem, "priority")) or None,
        assignee=_normalise_ws(_xml_text(elem, "assignee")) or None,
        reporter=_normalise_ws(_xml_text(elem, "reporter")) or None,
        epic_key=epic_key,
        parent_key=parent_key,
        due_date=_parse_iso_timestamp(_xml_text(elem, "due")) or None,
        created_at=_parse_iso_timestamp(_xml_text(elem, "created")),
        updated_at=_parse_iso_timestamp(_xml_text(elem, "updated")),
        source_url=source_url,
        labels=labels,
        components=components,
        sprints=sprints,
        links=links,
        comments=comments,
    )


# ────────────────────────────────────────────────────────────────────
# CSV parser
# ────────────────────────────────────────────────────────────────────


def _csv_read_header(path: Path) -> Tuple[List[str], Dict[str, List[int]]]:
    """Return the raw header list and a map {column_name: [indices]}.

    Jira CSV repeats columns like "Sprint", "Label", "Comment" — we
    capture every index for each name so all values are preserved.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            raise JiraImportError("CSV is empty")
    col_index: Dict[str, List[int]] = {}
    for i, name in enumerate(header):
        col_index.setdefault(name.strip(), []).append(i)
    return header, col_index


def _row_values(row: List[str], col_index: Dict[str, List[int]], name: str) -> List[str]:
    idxs = col_index.get(name)
    if not idxs:
        return []
    out: List[str] = []
    for i in idxs:
        if i < len(row):
            value = (row[i] or "").strip()
            if value:
                out.append(value)
    return out


def _row_first(row, col_index, name: str) -> str:
    vals = _row_values(row, col_index, name)
    return vals[0] if vals else ""


def iter_csv_issues(path: Path) -> Iterator[Issue]:
    header, col_index = _csv_read_header(path)

    key_col = None
    for candidate in ("Issue key", "Key"):
        if candidate in col_index:
            key_col = candidate
            break
    if key_col is None:
        raise JiraImportError("CSV is missing 'Issue key' column")

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        next(reader)  # skip header
        for row in reader:
            if not row or not any(cell.strip() for cell in row):
                continue
            try:
                yield _parse_csv_row(row, col_index, key_col)
            except JiraImportError as exc:
                logger.warning("Skipping CSV row: %s", exc)
                continue


def _parse_csv_row(row: List[str], col_index: Dict[str, List[int]], key_col: str) -> Issue:
    key = _row_first(row, col_index, key_col)
    _validate_issue_key(key)

    project_key = (
        _row_first(row, col_index, "Project key")
        or _project_from_key(key)
    )

    status = _row_first(row, col_index, "Status")
    issue_type = _row_first(row, col_index, "Issue Type") or "Task"

    labels = sorted(set(_row_values(row, col_index, "Labels")))
    components = sorted(set(_row_values(row, col_index, "Component/s")))

    sprint_names = _row_values(row, col_index, "Sprint")
    sprints = [Sprint(name=n) for n in sprint_names]

    links: List[Link] = []
    for csv_col, link_type in _CSV_LINK_COLS.items():
        for target in _row_values(row, col_index, csv_col):
            if ISSUE_KEY_RE.match(target):
                direction = "outbound" if csv_col.startswith("Outward") else "inbound"
                links.append(Link(target_key=target, link_type=link_type, direction=direction))

    comments = []
    for raw_comment in _row_values(row, col_index, "Comment"):
        # Jira CSV comments: "DD/MMM/YY HH:MM AM;author;body"
        parts = raw_comment.split(";", 2)
        if len(parts) == 3:
            created, author, body = parts
            comments.append(
                Comment(
                    author=author.strip() or None,
                    created_at=_parse_iso_timestamp(created.strip()),
                    body=_jira_markup_to_markdown(body.strip()),
                )
            )
        else:
            comments.append(Comment(author=None, created_at=None, body=_jira_markup_to_markdown(raw_comment)))

    epic_key = _row_first(row, col_index, "Custom field (Epic Link)") or None
    if epic_key and not ISSUE_KEY_RE.match(epic_key):
        epic_key = None

    parent_key = _row_first(row, col_index, "Parent") or None
    if parent_key and not ISSUE_KEY_RE.match(parent_key):
        parent_key = None

    return Issue(
        issue_key=key,
        project_key=project_key,
        title=_normalise_ws(_row_first(row, col_index, "Summary")),
        description=_jira_markup_to_markdown(_row_first(row, col_index, "Description")),
        issue_type=issue_type,
        status=status,
        status_category=_status_category(status),
        priority=_row_first(row, col_index, "Priority") or None,
        assignee=_row_first(row, col_index, "Assignee") or None,
        reporter=_row_first(row, col_index, "Reporter") or None,
        epic_key=epic_key,
        parent_key=parent_key,
        due_date=_parse_iso_timestamp(_row_first(row, col_index, "Due Date")) or None,
        created_at=_parse_iso_timestamp(_row_first(row, col_index, "Created")),
        updated_at=_parse_iso_timestamp(_row_first(row, col_index, "Updated")),
        source_url=None,
        labels=labels,
        components=components,
        sprints=sprints,
        links=links,
        comments=comments,
    )


# ────────────────────────────────────────────────────────────────────
# Markdown emission
# ────────────────────────────────────────────────────────────────────


def _build_tags(issue: Issue) -> List[str]:
    tags: List[str] = ["jira", f"jira/{issue.project_key}"]
    if issue.issue_type:
        tags.append(f"jira/{issue.issue_type.lower().replace(' ', '-')}")
    if issue.status_category:
        tags.append(f"jira/status/{issue.status_category}")
    return tags


def build_markdown(issue: Issue) -> str:
    """Render an Issue as a self-contained Markdown document.

    Frontmatter is ordered and stable so diffs are clean on re-import.
    """
    fm: Dict[str, Any] = {
        "title": f"{issue.issue_key} — {issue.title}" if issue.title else issue.issue_key,
        "issue_key": issue.issue_key,
        "project_key": issue.project_key,
        "type": "jira_issue",
        "issue_type": issue.issue_type,
        "status": issue.status,
        "status_category": issue.status_category or "",
        "priority": issue.priority or "",
        "assignee": issue.assignee or "",
        "reporter": issue.reporter or "",
        "epic": issue.epic_key or "",
        "parent": issue.parent_key or "",
        "sprint": issue.sprints[0].name if issue.sprints else "",
        "sprints": [s.name for s in issue.sprints],
        "labels": sorted(issue.labels),
        "components": sorted(issue.components),
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
        "due_date": issue.due_date or "",
        "source_url": issue.source_url or "",
        "tags": _build_tags(issue),
    }

    sections: List[str] = []
    heading = f"# {issue.issue_key} — {issue.title}" if issue.title else f"# {issue.issue_key}"
    sections.append(heading)

    if issue.description:
        sections.append("## Description\n\n" + issue.description)

    if issue.comments:
        comment_lines = ["## Comments"]
        for c in issue.comments:
            header = "### "
            parts = []
            if c.created_at:
                parts.append(c.created_at)
            if c.author:
                parts.append(c.author)
            header += " — ".join(parts) if parts else "comment"
            comment_lines.append(header)
            comment_lines.append(c.body)
        sections.append("\n\n".join(comment_lines))

    # Links section uses [[KEY]] wiki-links so the entity extractor picks them up.
    if issue.links or issue.epic_key or issue.parent_key:
        link_lines: List[str] = ["## Links"]
        if issue.epic_key:
            link_lines.append(f"- in epic: [[{issue.epic_key}]]")
        if issue.parent_key:
            link_lines.append(f"- parent: [[{issue.parent_key}]]")
        # Group links by type for stable output.
        grouped: Dict[str, List[str]] = {}
        for ln in issue.links:
            grouped.setdefault(ln.link_type, []).append(ln.target_key)
        for link_type in sorted(grouped):
            targets = sorted(set(grouped[link_type]))
            link_lines.append(f"- {link_type}: " + ", ".join(f"[[{t}]]" for t in targets))
        sections.append("\n".join(link_lines))

    body = "\n\n".join(sections).strip() + "\n"
    return add_frontmatter(body, fm)


def _atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


# ────────────────────────────────────────────────────────────────────
# Persistence
# ────────────────────────────────────────────────────────────────────


def _workspace_paths(workspace_path: Optional[Path]) -> Tuple[Path, Path]:
    base = workspace_path or get_settings().workspace_path
    return base, base / "app" / "jarvis.db"


async def _upsert_issue(db: aiosqlite.Connection, issue: Issue, now: str) -> str:
    """Insert or replace an issue row plus all m2m rows. Returns "inserted"/"updated"."""
    cursor = await db.execute(
        "SELECT content_hash FROM issues WHERE issue_key = ?", (issue.issue_key,)
    )
    row = await cursor.fetchone()
    existed = row is not None

    await db.execute(
        """
        INSERT INTO issues (
            issue_key, project_key, title, description, issue_type,
            status, status_category, priority, assignee, reporter,
            epic_key, parent_key, due_date, created_at, updated_at,
            source_url, note_path, content_hash, imported_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(issue_key) DO UPDATE SET
            project_key=excluded.project_key,
            title=excluded.title,
            description=excluded.description,
            issue_type=excluded.issue_type,
            status=excluded.status,
            status_category=excluded.status_category,
            priority=excluded.priority,
            assignee=excluded.assignee,
            reporter=excluded.reporter,
            epic_key=excluded.epic_key,
            parent_key=excluded.parent_key,
            due_date=excluded.due_date,
            created_at=excluded.created_at,
            updated_at=excluded.updated_at,
            source_url=excluded.source_url,
            note_path=excluded.note_path,
            content_hash=excluded.content_hash,
            imported_at=excluded.imported_at
        """,
        (
            issue.issue_key,
            issue.project_key,
            issue.title,
            issue.description,
            issue.issue_type,
            issue.status,
            issue.status_category,
            issue.priority,
            issue.assignee,
            issue.reporter,
            issue.epic_key,
            issue.parent_key,
            issue.due_date,
            issue.created_at,
            issue.updated_at,
            issue.source_url,
            issue.note_path,
            issue.content_hash(),
            now,
        ),
    )

    # Replace m2m sets (delete + insert — simpler than diffing, tables are tiny).
    await db.execute("DELETE FROM issue_labels WHERE issue_key = ?", (issue.issue_key,))
    if issue.labels:
        await db.executemany(
            "INSERT OR IGNORE INTO issue_labels(issue_key, label) VALUES(?, ?)",
            [(issue.issue_key, l) for l in sorted(set(issue.labels))],
        )

    await db.execute(
        "DELETE FROM issue_components WHERE issue_key = ?", (issue.issue_key,)
    )
    if issue.components:
        await db.executemany(
            "INSERT OR IGNORE INTO issue_components(issue_key, component) VALUES(?, ?)",
            [(issue.issue_key, c) for c in sorted(set(issue.components))],
        )

    await db.execute(
        "DELETE FROM issue_sprints WHERE issue_key = ?", (issue.issue_key,)
    )
    if issue.sprints:
        seen = set()
        for s in issue.sprints:
            if s.name in seen:
                continue
            seen.add(s.name)
            await db.execute(
                "INSERT OR IGNORE INTO issue_sprints(issue_key, sprint_name, sprint_state) VALUES(?, ?, ?)",
                (issue.issue_key, s.name, s.state),
            )

    # Outbound links keyed by this issue. Inbound links land on the target
    # issue's row when it is processed; we still record them so the raw
    # view is complete regardless of import order.
    await db.execute(
        "DELETE FROM issue_links WHERE source_key = ?", (issue.issue_key,)
    )
    if issue.links:
        seen_links = set()
        for ln in issue.links:
            tup = (issue.issue_key, ln.target_key, ln.link_type, ln.direction)
            if tup in seen_links:
                continue
            seen_links.add(tup)
            await db.execute(
                """INSERT OR IGNORE INTO issue_links(
                    source_key, target_key, link_type, direction
                ) VALUES(?, ?, ?, ?)""",
                tup,
            )

    await db.execute("DELETE FROM issue_comments WHERE issue_key = ?", (issue.issue_key,))
    if issue.comments:
        await db.executemany(
            """INSERT INTO issue_comments(issue_key, author, created_at, body)
               VALUES(?, ?, ?, ?)""",
            [
                (issue.issue_key, c.author, c.created_at, c.body)
                for c in issue.comments
            ],
        )

    return "updated" if existed else "inserted"


# ────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────


def detect_format(path: Path, declared: Optional[str] = None) -> str:
    if declared:
        declared = declared.lower()
        if declared in ("xml", "csv"):
            return declared
    ext = path.suffix.lower()
    if ext == ".xml":
        return "xml"
    if ext == ".csv":
        return "csv"
    # Sniff the first byte.
    try:
        with path.open("rb") as fh:
            head = fh.read(512).lstrip()
    except OSError:
        raise JiraImportError(f"Cannot read file: {path.name}")
    if head.startswith(b"<?xml") or head.startswith(b"<rss"):
        return "xml"
    return "csv"


def iter_issues(path: Path, fmt: str) -> Iterator[Issue]:
    if fmt == "xml":
        return iter_xml_issues(path)
    if fmt == "csv":
        return iter_csv_issues(path)
    raise JiraImportError(f"Unsupported format: {fmt}")


async def run_import(
    file_path: Path,
    *,
    filename: Optional[str] = None,
    fmt: Optional[str] = None,
    project_filter: Optional[List[str]] = None,
    workspace_path: Optional[Path] = None,
) -> ImportStats:
    """Import a Jira export. Idempotent by (issue_key, content_hash).

    Yields-free variant used for tests and programmatic calls.
    """
    workspace, db_path = _workspace_paths(workspace_path)
    memory_dir = workspace / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    await init_database(db_path)

    resolved_fmt = detect_format(file_path, fmt)
    display_name = filename or file_path.name
    stats = ImportStats()
    started = datetime.now(timezone.utc)
    allowed_projects = {p.strip().upper() for p in (project_filter or []) if p.strip()}

    # Create the import row up-front so the SSE stream can reference it.
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        cursor = await db.execute(
            """INSERT INTO jira_imports(
                filename, format, project_keys, status, started_at
            ) VALUES(?, ?, ?, 'running', ?)""",
            (display_name, resolved_fmt, "[]", started.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        import_id = cursor.lastrowid
        await db.commit()

    project_keys_seen: set = set()
    error_message: Optional[str] = None

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            for issue in iter_issues(file_path, resolved_fmt):
                if allowed_projects and issue.project_key.upper() not in allowed_projects:
                    continue
                stats.issue_count += 1
                project_keys_seen.add(issue.project_key)

                new_hash = issue.content_hash()
                cursor = await db.execute(
                    "SELECT content_hash FROM issues WHERE issue_key = ?",
                    (issue.issue_key,),
                )
                row = await cursor.fetchone()
                if row and row[0] == new_hash:
                    # Ensure the Markdown file still exists (user may have deleted it).
                    md_path = workspace / issue.note_path
                    if md_path.exists():
                        stats.skipped += 1
                        continue

                # Write Markdown first — it is the source of truth.
                md_path = workspace / issue.note_path
                _atomic_write_text(md_path, build_markdown(issue))

                result = await _upsert_issue(db, issue, now_iso)
                if result == "inserted":
                    stats.inserted += 1
                else:
                    stats.updated += 1

                # Commit in small batches for crash safety on huge imports.
                if (stats.inserted + stats.updated) % 50 == 0:
                    await db.commit()

            await db.commit()
            stats.bytes_processed = file_path.stat().st_size
            stats.project_keys = sorted(project_keys_seen)

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        logger.exception("Jira import failed")
        raise
    finally:
        finished = datetime.now(timezone.utc)
        duration_ms = int((finished - started).total_seconds() * 1000)
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute(
                """UPDATE jira_imports SET
                    project_keys=?, issue_count=?, inserted=?, updated=?,
                    skipped=?, bytes_processed=?, duration_ms=?,
                    status=?, error=?, finished_at=?
                WHERE id=?""",
                (
                    json.dumps(sorted(project_keys_seen)),
                    stats.issue_count,
                    stats.inserted,
                    stats.updated,
                    stats.skipped,
                    stats.bytes_processed,
                    duration_ms,
                    "failed" if error_message else "done",
                    error_message,
                    finished.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    import_id,
                ),
            )
            await db.commit()

    return stats


async def list_imports(
    *, limit: int = 50, workspace_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    _, db_path = _workspace_paths(workspace_path)
    if not db_path.exists():
        return []
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, filename, format, project_keys, issue_count,
                      inserted, updated, skipped, bytes_processed,
                      duration_ms, status, error, started_at, finished_at
               FROM jira_imports ORDER BY id DESC LIMIT ?""",
            (int(limit),),
        )
        rows = await cursor.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["project_keys"] = json.loads(d.get("project_keys") or "[]")
        except json.JSONDecodeError:
            d["project_keys"] = []
        out.append(d)
    return out


async def list_issues(
    *,
    project: Optional[str] = None,
    status_category: Optional[str] = None,
    assignee: Optional[str] = None,
    sprint: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    workspace_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    _, db_path = _workspace_paths(workspace_path)
    if not db_path.exists():
        return []
    where: List[str] = []
    params: List[Any] = []
    if project:
        where.append("i.project_key = ?")
        params.append(project.strip().upper())
    if status_category:
        where.append("i.status_category = ?")
        params.append(status_category.strip().lower())
    if assignee:
        where.append("i.assignee = ?")
        params.append(assignee.strip())
    join = ""
    if sprint:
        join = "JOIN issue_sprints s ON s.issue_key = i.issue_key"
        where.append("s.sprint_name = ?")
        params.append(sprint.strip())
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT i.issue_key, i.project_key, i.title, i.issue_type, i.status,
               i.status_category, i.priority, i.assignee, i.reporter,
               i.epic_key, i.updated_at, i.note_path
        FROM issues i {join}
        {where_sql}
        ORDER BY i.updated_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([int(limit), int(offset)])
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]
