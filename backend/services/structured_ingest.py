"""Ingest structured data files (CSV, XML) into Jarvis memory.

Optimized for Jira exports but handles generic CSV/XML too.
Large files are streamed (no full-DOM / no full-read) and split into
grouped markdown notes with entity extraction for the knowledge graph.
"""

import csv
import logging
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from config import get_settings

logger = logging.getLogger(__name__)

# Jira often exports description / comment fields well above the default
# csv field size limit (~131 KB). Raise it once at import time to the
# platform maximum so large cells don't crash parsing.
def _raise_csv_field_limit() -> None:
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


_raise_csv_field_limit()

# Encodings to try for CSV files, in order. utf-8-sig strips a BOM if present
# (common in Jira Cloud exports). cp1252 is a fallback for older Jira Server.
_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def _open_text_stream(file_path: Path) -> Tuple[TextIO, str]:
    """Open a file for text reading, auto-detecting encoding.

    Returns (file_handle, encoding_used). Caller must close the handle.
    """
    for enc in _CSV_ENCODINGS:
        try:
            fh = file_path.open("r", encoding=enc, newline="")
            # Force a small read to trigger decode errors early
            head = fh.read(4096)
            fh.seek(0)
            _ = head  # unused, just for side-effect
            return fh, enc
        except UnicodeDecodeError:
            continue
    # Last resort: replace errors
    return file_path.open("r", encoding="utf-8", errors="replace", newline=""), "utf-8-replace"

# Jira CSV column names (case-insensitive matching)
JIRA_KEY_COLUMNS = {
    "issue key", "issue id", "key", "issue_key",
}
JIRA_SUMMARY_COLUMNS = {"summary", "title"}
JIRA_TYPE_COLUMNS = {"issue type", "issuetype", "type"}
JIRA_STATUS_COLUMNS = {"status"}
JIRA_PRIORITY_COLUMNS = {"priority"}
JIRA_ASSIGNEE_COLUMNS = {"assignee"}
JIRA_REPORTER_COLUMNS = {"reporter", "creator"}
JIRA_EPIC_COLUMNS = {"epic link", "epic name", "epic", "custom field (epic link)", "custom field (epic name)"}
JIRA_SPRINT_COLUMNS = {"sprint"}
JIRA_LABELS_COLUMNS = {"labels", "label"}
JIRA_COMPONENTS_COLUMNS = {"components", "component", "component/s"}
JIRA_PARENT_COLUMNS = {"parent", "parent id"}
JIRA_DESCRIPTION_COLUMNS = {"description"}
JIRA_CREATED_COLUMNS = {"created", "created date"}
JIRA_UPDATED_COLUMNS = {"updated", "updated date", "resolved"}
JIRA_FIX_VERSION_COLUMNS = {"fix version", "fix version/s"}
JIRA_PROJECT_COLUMNS = {"project", "project key", "project name"}
JIRA_LINKED_ISSUES_COLUMNS = {
    "linked issues", "outward issue link", "inward issue link",
    "outward issue link (blocks)", "inward issue link (blocks)",
    "outward issue link (is blocked by)", "inward issue link (is blocked by)",
    "outward issue link (clones)", "inward issue link (clones)",
    "outward issue link (relates to)", "inward issue link (relates to)",
    "outward issue link (duplicates)", "inward issue link (duplicates)",
}
JIRA_COMMENTS_COLUMNS = {"comment", "comments", "comment body"}


@dataclass
class JiraIssue:
    key: str
    summary: str
    issue_type: str = ""
    status: str = ""
    priority: str = ""
    assignee: str = ""
    reporter: str = ""
    epic: str = ""
    sprint: str = ""
    labels: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    parent: str = ""
    description: str = ""
    created: str = ""
    updated: str = ""
    fix_version: str = ""
    project: str = ""
    linked_issues: List[str] = field(default_factory=list)
    comments: str = ""
    extra_fields: Dict[str, str] = field(default_factory=dict)


def _find_column(headers: List[str], candidates: set) -> Optional[int]:
    """Find column index matching any of the candidate names (case-insensitive)."""
    for i, h in enumerate(headers):
        if h.strip().lower() in candidates:
            return i
    return None


def _find_all_columns(headers: List[str], candidates: set) -> List[int]:
    """Find all column indices matching candidate names."""
    return [i for i, h in enumerate(headers) if h.strip().lower() in candidates]


def _split_multi_value(value: str) -> List[str]:
    """Split comma/semicolon-separated values, stripping whitespace."""
    if not value.strip():
        return []
    parts = re.split(r"[;,]", value)
    return [p.strip() for p in parts if p.strip()]


def _detect_jira_csv(headers: List[str]) -> bool:
    """Check if CSV headers look like a Jira export."""
    lower = {h.strip().lower() for h in headers}
    jira_indicators = {"issue key", "summary", "status", "issue type",
                       "issuetype", "assignee", "priority", "key"}
    return len(lower & jira_indicators) >= 3


def _detect_jira_xml(root: ET.Element) -> bool:
    """Check if XML root looks like a Jira RSS/XML export."""
    # Jira exports as RSS with <channel><item> elements
    if root.tag == "rss":
        return True
    # Or direct <items> / <item> with <key> children
    for child in root.iter():
        if child.tag in ("item", "issue"):
            for sub in child:
                if sub.tag == "key":
                    return True
            break
    return False


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def parse_csv_file(file_path: Path, encoding: Optional[str] = None) -> Tuple[List[str], List[JiraIssue], bool]:
    """Parse CSV file. Returns (headers, issues, is_jira).

    Streams the file row-by-row so large Jira exports don't need to fit
    in memory. For non-Jira CSVs, issues is empty and headers are
    returned for generic processing.
    """
    # Open with auto-detected encoding (handles Jira Cloud UTF-8 BOM and
    # legacy cp1252 Server exports).
    if encoding:
        fh: TextIO = file_path.open("r", encoding=encoding, errors="replace", newline="")
    else:
        fh, _ = _open_text_stream(file_path)

    try:
        # Sniff delimiter from a sample, then rewind.
        sample = fh.read(16384)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(fh, dialect)
        try:
            headers = next(reader)
        except StopIteration:
            return [], [], False

        # Strip any leftover BOM on the first header (belt-and-braces).
        if headers and headers[0].startswith("\ufeff"):
            headers[0] = headers[0].lstrip("\ufeff")

        is_jira = _detect_jira_csv(headers)
        if not is_jira:
            return headers, [], False

        # Single-value columns (first match wins)
        key_idx = _find_column(headers, JIRA_KEY_COLUMNS)
        summary_idx = _find_column(headers, JIRA_SUMMARY_COLUMNS)
        type_idx = _find_column(headers, JIRA_TYPE_COLUMNS)
        status_idx = _find_column(headers, JIRA_STATUS_COLUMNS)
        priority_idx = _find_column(headers, JIRA_PRIORITY_COLUMNS)
        assignee_idx = _find_column(headers, JIRA_ASSIGNEE_COLUMNS)
        reporter_idx = _find_column(headers, JIRA_REPORTER_COLUMNS)
        epic_idx = _find_column(headers, JIRA_EPIC_COLUMNS)
        parent_idx = _find_column(headers, JIRA_PARENT_COLUMNS)
        desc_idx = _find_column(headers, JIRA_DESCRIPTION_COLUMNS)
        created_idx = _find_column(headers, JIRA_CREATED_COLUMNS)
        updated_idx = _find_column(headers, JIRA_UPDATED_COLUMNS)
        project_idx = _find_column(headers, JIRA_PROJECT_COLUMNS)

        # Multi-value columns: Jira repeats the header for each value
        # (e.g. 10+ "Comment" columns, multiple "Labels", "Components",
        # "Fix Version/s", "Sprint"). Collect them all.
        sprint_idxs = _find_all_columns(headers, JIRA_SPRINT_COLUMNS)
        labels_idxs = _find_all_columns(headers, JIRA_LABELS_COLUMNS)
        components_idxs = _find_all_columns(headers, JIRA_COMPONENTS_COLUMNS)
        fix_ver_idxs = _find_all_columns(headers, JIRA_FIX_VERSION_COLUMNS)
        linked_idxs = _find_all_columns(headers, JIRA_LINKED_ISSUES_COLUMNS)
        comment_idxs = _find_all_columns(headers, JIRA_COMMENTS_COLUMNS)

        known_idxs = {idx for idx in [
            key_idx, summary_idx, type_idx, status_idx, priority_idx,
            assignee_idx, reporter_idx, epic_idx, parent_idx, desc_idx,
            created_idx, updated_idx, project_idx,
        ] if idx is not None}
        known_idxs.update(sprint_idxs, labels_idxs, components_idxs,
                          fix_ver_idxs, linked_idxs, comment_idxs)

        def _get(row: List[str], idx: Optional[int]) -> str:
            if idx is None or idx >= len(row):
                return ""
            return row[idx].strip()

        def _collect(row: List[str], idxs: List[int]) -> List[str]:
            out: List[str] = []
            for i in idxs:
                if i < len(row):
                    v = row[i].strip()
                    if v:
                        out.append(v)
            return out

        issues: List[JiraIssue] = []
        for row in reader:
            if not any(c.strip() for c in row):
                continue  # skip empty rows

            key_val = _get(row, key_idx)
            summary_val = _get(row, summary_idx)
            if not key_val and not summary_val:
                continue

            # Merge all comment columns into one block
            comment_cells = _collect(row, comment_idxs)
            comments_text = "\n\n---\n\n".join(comment_cells) if comment_cells else ""

            # Labels / components / fix versions: flatten and split
            labels: List[str] = []
            for cell in _collect(row, labels_idxs):
                labels.extend(_split_multi_value(cell))
            components: List[str] = []
            for cell in _collect(row, components_idxs):
                components.extend(_split_multi_value(cell))
            fix_versions: List[str] = []
            for cell in _collect(row, fix_ver_idxs):
                fix_versions.extend(_split_multi_value(cell))
            sprints = _collect(row, sprint_idxs)

            # Linked issues — dedupe preserving order
            links: List[str] = []
            seen_links = set()
            for cell in _collect(row, linked_idxs):
                for v in _split_multi_value(cell):
                    if v not in seen_links:
                        seen_links.add(v)
                        links.append(v)

            # Extra fields (excluding already-consumed columns)
            extra: Dict[str, str] = {}
            for i, h in enumerate(headers):
                if i in known_idxs or i >= len(row):
                    continue
                val = row[i].strip()
                if val:
                    extra[h.strip()] = val

            issues.append(JiraIssue(
                key=key_val or summary_val[:30],
                summary=summary_val,
                issue_type=_get(row, type_idx),
                status=_get(row, status_idx),
                priority=_get(row, priority_idx),
                assignee=_get(row, assignee_idx),
                reporter=_get(row, reporter_idx),
                epic=_get(row, epic_idx),
                sprint=", ".join(sprints),
                labels=labels,
                components=components,
                parent=_get(row, parent_idx),
                description=_get(row, desc_idx),
                created=_get(row, created_idx),
                updated=_get(row, updated_idx),
                fix_version=", ".join(fix_versions),
                project=_get(row, project_idx),
                linked_issues=links,
                comments=comments_text,
                extra_fields=extra,
            ))

        return headers, issues, True
    finally:
        fh.close()


# ---------------------------------------------------------------------------
# XML parsing (Jira RSS export)
# ---------------------------------------------------------------------------

def _xml_text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _parse_jira_xml_item(item: ET.Element) -> JiraIssue:
    """Parse a single <item> from Jira RSS XML."""
    key = _xml_text(item.find("key"))
    summary = _xml_text(item.find("summary")) or _xml_text(item.find("title"))

    # Type, status, priority, assignee, reporter
    type_el = item.find("type")
    status_el = item.find("status")
    priority_el = item.find("priority")
    assignee_el = item.find("assignee")
    reporter_el = item.find("reporter")

    # Labels
    labels = [_xml_text(l) for l in item.findall("labels/label") if _xml_text(l)]

    # Components
    components = [_xml_text(c) for c in item.findall("component") if _xml_text(c)]

    # Fix versions
    fix_versions = [_xml_text(v) for v in item.findall("fixVersion") if _xml_text(v)]

    # Description
    description = _xml_text(item.find("description"))

    # Comments
    comment_parts = []
    for comment in item.findall(".//comment"):
        author = comment.get("author", "")
        body = _xml_text(comment)
        if body:
            comment_parts.append(f"**{author}**: {body}" if author else body)

    # Linked issues (dedupe). Jira RSS wraps them in
    # <issuelinks>/<issuelinktype>/<outwardlinks|inwardlinks>/<issuelink>/<issuekey>.
    # We deliberately do NOT fall back to scanning every <issuekey> under the
    # item, since that also matches subtask references and produces duplicates.
    links: List[str] = []
    seen_links = set()
    for link_type in item.findall(".//issuelinktype"):
        for direction in ("outwardlinks", "inwardlinks"):
            for linked in link_type.findall(f"{direction}/issuelink/issuekey"):
                v = (linked.text or "").strip()
                if v and v != key and v not in seen_links:
                    seen_links.add(v)
                    links.append(v)
    # Subtasks as a separate relation source
    for st in item.findall(".//subtasks/subtask"):
        v = (st.text or "").strip()
        if v and v != key and v not in seen_links:
            seen_links.add(v)
            links.append(v)

    # Custom fields (epic, sprint etc.)
    epic = ""
    sprint = ""
    for cf in item.findall(".//customfield"):
        cf_name = _xml_text(cf.find("customfieldname"))
        cf_val_el = cf.find("customfieldvalues/customfieldvalue")
        cf_val = _xml_text(cf_val_el) if cf_val_el is not None else ""
        if cf_name.lower() in ("epic link", "epic name"):
            epic = cf_val
        elif cf_name.lower() == "sprint":
            sprint = cf_val

    # Parent
    parent = _xml_text(item.find("parent"))

    # Project
    project = _xml_text(item.find("project"))

    return JiraIssue(
        key=key or summary[:30],
        summary=summary,
        issue_type=_xml_text(type_el),
        status=_xml_text(status_el),
        priority=_xml_text(priority_el),
        assignee=_xml_text(assignee_el),
        reporter=_xml_text(reporter_el),
        epic=epic,
        sprint=sprint,
        labels=labels,
        components=components,
        parent=parent,
        description=description,
        created=_xml_text(item.find("created")),
        updated=_xml_text(item.find("updated")),
        fix_version=", ".join(fix_versions),
        project=project,
        linked_issues=links,
        comments="\n\n".join(comment_parts),
    )


def parse_xml_file(file_path: Path) -> Tuple[List[JiraIssue], bool]:
    """Parse XML file. Returns (issues, is_jira).

    Streams the document with :func:`xml.etree.ElementTree.iterparse` so
    large Jira exports (hundreds of MB) don't need to fit in memory.
    Each <item>/<issue> element is processed then cleared.
    """
    issues: List[JiraIssue] = []
    is_jira = False
    root_tag: Optional[str] = None

    try:
        context = ET.iterparse(str(file_path), events=("start", "end"))
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    try:
        for event, elem in context:
            if event == "start" and root_tag is None:
                root_tag = elem.tag
                if root_tag == "rss":
                    is_jira = True
                continue

            if event != "end":
                continue

            tag = elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag

            if tag in ("item", "issue"):
                # Probe: does this element look like a Jira item?
                if not is_jira:
                    if elem.find("key") is not None and (
                        elem.find("summary") is not None or elem.find("title") is not None
                    ):
                        is_jira = True

                if is_jira:
                    try:
                        issues.append(_parse_jira_xml_item(elem))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to parse XML item: %s", exc)

                # Free memory: drop parsed element and any preceding siblings
                elem.clear()
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    if not issues and not is_jira:
        return [], False
    return issues, True


# ---------------------------------------------------------------------------
# Markdown generation — grouped by epic/project
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def _issue_to_row(issue: JiraIssue) -> str:
    """Format a single issue as a markdown section."""
    lines = []
    lines.append(f"### {issue.key}: {issue.summary}")
    lines.append("")

    meta_parts = []
    if issue.issue_type:
        meta_parts.append(f"**Type:** {issue.issue_type}")
    if issue.status:
        meta_parts.append(f"**Status:** {issue.status}")
    if issue.priority:
        meta_parts.append(f"**Priority:** {issue.priority}")
    if issue.assignee:
        meta_parts.append(f"**Assignee:** {issue.assignee}")
    if issue.reporter:
        meta_parts.append(f"**Reporter:** {issue.reporter}")
    if issue.sprint:
        meta_parts.append(f"**Sprint:** {issue.sprint}")
    if issue.parent:
        meta_parts.append(f"**Parent:** {issue.parent}")
    if issue.fix_version:
        meta_parts.append(f"**Fix Version:** {issue.fix_version}")
    if issue.created:
        meta_parts.append(f"**Created:** {issue.created}")
    if issue.updated:
        meta_parts.append(f"**Updated:** {issue.updated}")
    if issue.labels:
        meta_parts.append(f"**Labels:** {', '.join(issue.labels)}")
    if issue.components:
        meta_parts.append(f"**Components:** {', '.join(issue.components)}")
    if issue.linked_issues:
        meta_parts.append(f"**Linked:** {', '.join(issue.linked_issues)}")

    if meta_parts:
        lines.append(" | ".join(meta_parts))
        lines.append("")

    if issue.description:
        # Truncate very long descriptions
        desc = issue.description[:2000]
        if len(issue.description) > 2000:
            desc += "\n\n*(truncated)*"
        lines.append(desc)
        lines.append("")

    if issue.comments:
        lines.append("**Comments:**")
        lines.append("")
        lines.append(issue.comments[:1000])
        lines.append("")

    # Extra fields
    for k, v in issue.extra_fields.items():
        if len(v) < 200:  # Skip very long custom fields inline
            lines.append(f"**{k}:** {v}")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _group_issues(issues: List[JiraIssue]) -> Dict[str, List[JiraIssue]]:
    """Group issues by epic, then by project, then ungrouped."""
    groups: Dict[str, List[JiraIssue]] = {}
    for issue in issues:
        group_key = issue.epic or issue.project or "ungrouped"
        groups.setdefault(group_key, []).append(issue)
    return groups


def _build_summary_note(
    issues: List[JiraIssue],
    source_name: str,
    groups: Dict[str, List[JiraIssue]],
) -> str:
    """Build an overview/summary note for the entire export."""
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Collect all unique people, statuses, types
    people = set()
    statuses: Dict[str, int] = {}
    types: Dict[str, int] = {}
    projects = set()
    for issue in issues:
        if issue.assignee:
            people.add(issue.assignee)
        if issue.reporter:
            people.add(issue.reporter)
        if issue.project:
            projects.add(issue.project)
        statuses[issue.status] = statuses.get(issue.status, 0) + 1
        if issue.issue_type:
            types[issue.issue_type] = types.get(issue.issue_type, 0) + 1

    tags = ["jira", "import", "overview"]
    tags.extend(p.lower().replace(" ", "-") for p in projects if p)

    fm = {
        "title": f"Jira Export: {source_name}",
        "date": now,
        "source": source_name,
        "type": "jira-export-overview",
        "tags": tags,
        "total_issues": len(issues),
    }

    body_lines = [
        f"# Jira Export Overview: {source_name}",
        "",
        f"**Total issues:** {len(issues)}",
        f"**Groups (epics/projects):** {len(groups)}",
        f"**People involved:** {len(people)}",
        "",
    ]

    # Status breakdown
    if statuses:
        body_lines.append("## Status Breakdown")
        body_lines.append("")
        for s, count in sorted(statuses.items(), key=lambda x: -x[1]):
            body_lines.append(f"- **{s or 'No Status'}**: {count}")
        body_lines.append("")

    # Type breakdown
    if types:
        body_lines.append("## Issue Types")
        body_lines.append("")
        for t, count in sorted(types.items(), key=lambda x: -x[1]):
            body_lines.append(f"- **{t}**: {count}")
        body_lines.append("")

    # People
    if people:
        body_lines.append("## People")
        body_lines.append("")
        for p in sorted(people):
            body_lines.append(f"- [[{p}]]")
        body_lines.append("")

    # Groups listing
    body_lines.append("## Groups")
    body_lines.append("")
    for group_name, group_issues in sorted(groups.items()):
        body_lines.append(f"- **{group_name}** ({len(group_issues)} issues)")
    body_lines.append("")

    return add_frontmatter("\n".join(body_lines), fm)


def _build_group_note(
    group_name: str,
    issues: List[JiraIssue],
    source_name: str,
    max_issues_per_note: int = 100,
) -> List[Tuple[str, str]]:
    """Build markdown note(s) for a group of issues.

    Returns list of (filename, content) tuples.
    If a group is very large, it's split into multiple notes.
    """
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results: List[Tuple[str, str]] = []
    slug = _slugify(group_name) or "ungrouped"

    # Collect tags from issues in this group
    all_labels = set()
    all_people = set()
    for issue in issues:
        all_labels.update(issue.labels)
        if issue.assignee:
            all_people.add(issue.assignee)
        if issue.reporter:
            all_people.add(issue.reporter)

    # Split into chunks if too many issues
    chunks = [issues[i:i + max_issues_per_note]
              for i in range(0, len(issues), max_issues_per_note)]

    for chunk_idx, chunk in enumerate(chunks):
        suffix = f"-part-{chunk_idx + 1}" if len(chunks) > 1 else ""
        filename = f"jira-{slug}{suffix}.md"

        tags = ["jira", "import"]
        tags.extend(l.lower().replace(" ", "-") for l in list(all_labels)[:10])

        title = f"Jira: {group_name}"
        if len(chunks) > 1:
            title += f" (Part {chunk_idx + 1})"

        fm = {
            "title": title,
            "date": now,
            "source": source_name,
            "type": "jira-export",
            "group": group_name,
            "tags": tags,
            "issue_count": len(chunk),
        }

        body_lines = [f"# {title}", ""]

        # People involved (with wiki-links for graph)
        chunk_people = set()
        for issue in chunk:
            if issue.assignee:
                chunk_people.add(issue.assignee)
            if issue.reporter:
                chunk_people.add(issue.reporter)
        if chunk_people:
            body_lines.append("**People:** " + ", ".join(f"[[{p}]]" for p in sorted(chunk_people)))
            body_lines.append("")

        # Issues
        for issue in chunk:
            body_lines.append(_issue_to_row(issue))

        content = add_frontmatter("\n".join(body_lines), fm)
        results.append((filename, content))

    return results


def _build_generic_csv_note(
    file_path: Path,
    headers: List[str],
    source_name: str,
    max_rows: int = 500,
) -> Tuple[str, str]:
    """Build a markdown note from a non-Jira CSV file.

    Streams the file; converts the first ``max_rows`` rows to a markdown
    table and reports how many rows were skipped.
    """
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fh, _ = _open_text_stream(file_path)
    try:
        sample = fh.read(16384)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel

        reader = csv.reader(fh, dialect)
        try:
            parsed_headers = next(reader)
        except StopIteration:
            return _slugify(source_name) + ".md", ""

        if parsed_headers and parsed_headers[0].startswith("\ufeff"):
            parsed_headers[0] = parsed_headers[0].lstrip("\ufeff")
        headers = parsed_headers

        data_rows: List[List[str]] = []
        total_rows = 0
        for row in reader:
            total_rows += 1
            if len(data_rows) < max_rows:
                data_rows.append(row)
    finally:
        fh.close()

    truncated = total_rows > max_rows

    fm = {
        "title": f"CSV Import: {source_name}",
        "date": now,
        "source": source_name,
        "type": "csv-import",
        "tags": ["csv", "import", "data"],
        "columns": len(headers),
        "rows": total_rows,
    }

    body_lines = [f"# {source_name}", ""]
    body_lines.append(f"**Columns:** {len(headers)} | **Rows:** {total_rows}")
    body_lines.append("")

    # Markdown table
    body_lines.append("| " + " | ".join(h.strip() for h in headers) + " |")
    body_lines.append("| " + " | ".join("---" for _ in headers) + " |")

    for row in data_rows:
        cells = []
        for i, _h in enumerate(headers):
            val = row[i].strip() if i < len(row) else ""
            val = val.replace("|", "\\|").replace("\n", " ")
            if len(val) > 100:
                val = val[:97] + "..."
            cells.append(val)
        body_lines.append("| " + " | ".join(cells) + " |")

    if truncated:
        body_lines.append("")
        body_lines.append(f"*(Showing first {max_rows} of {total_rows} rows)*")

    body_lines.append("")
    content = add_frontmatter("\n".join(body_lines), fm)
    filename = _slugify(source_name) + ".md"
    return filename, content


def _build_generic_xml_note(file_path: Path, source_name: str) -> Tuple[str, str]:
    """Build a markdown note from a non-Jira XML file.

    Streams the document with iterparse so large files don't need to fit
    in memory. Captures the root tag, child-element counts, and renders
    up to ``max_items`` direct children in detail.
    """
    from utils.markdown import add_frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    root_tag: Optional[str] = None
    child_counts: Dict[str, int] = {}
    rendered_blocks: List[str] = []
    max_items = 200
    rendered = 0

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    try:
        context = ET.iterparse(str(file_path), events=("start", "end"))
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    depth = 0
    for event, elem in context:
        if event == "start":
            if root_tag is None:
                root_tag = _local(elem.tag)
            depth += 1
            continue

        # event == "end"
        depth -= 1
        # Only care about direct children of the root (depth == 1 after dec)
        if depth == 1:
            tag = _local(elem.tag)
            child_counts[tag] = child_counts.get(tag, 0) + 1

            if rendered < max_items:
                lines: List[str] = [f"### {tag}", ""]
                if elem.attrib:
                    for k, v in elem.attrib.items():
                        lines.append(f"- **{k}:** {v}")
                if elem.text and elem.text.strip():
                    lines.append(elem.text.strip()[:500])
                for sub in list(elem):
                    sub_tag = _local(sub.tag)
                    sub_text = (sub.text or "").strip()
                    if sub_text:
                        lines.append(f"- **{sub_tag}:** {sub_text[:200]}")
                    elif len(list(sub)) > 0:
                        lines.append(f"- **{sub_tag}:** ({len(list(sub))} sub-elements)")
                lines.append("")
                lines.append("---")
                lines.append("")
                rendered_blocks.append("\n".join(lines))
                rendered += 1

            elem.clear()
        elif depth == 0:
            # We just finished the root element; stop.
            elem.clear()
            break

    if root_tag is None:
        raise ValueError("Empty XML document")

    fm = {
        "title": f"XML Import: {source_name}",
        "date": now,
        "source": source_name,
        "type": "xml-import",
        "tags": ["xml", "import", "data"],
        "root_element": root_tag,
    }

    body_lines = [f"# {source_name}", ""]
    body_lines.append(f"**Root element:** `{root_tag}`")
    body_lines.append("")

    if child_counts:
        body_lines.append("## Structure")
        body_lines.append("")
        for tag, count in sorted(child_counts.items()):
            body_lines.append(f"- `{tag}`: {count} elements")
        body_lines.append("")

    body_lines.extend(rendered_blocks)
    total = sum(child_counts.values())
    if total > max_items:
        body_lines.append(f"*(Showing first {max_items} of {total} elements)*")

    content = add_frontmatter("\n".join(body_lines), fm)
    filename = _slugify(source_name) + ".md"
    return filename, content


    total = sum(child_counts.values())
    if total > max_items:
        body_lines.append(f"*(Showing first {max_items} of {total} elements)*")

    content = add_frontmatter("\n".join(body_lines), fm)
    filename = _slugify(source_name) + ".md"
    return filename, content


# ── Step 27d — large XML section split ───────────────────────────────────────

# Cap on the rendered size of any single XML section body so a single huge
# child element can't blow up a note. Anything beyond this is truncated
# with a marker.
_XML_SECTION_TRUNCATE = 60_000


def _build_xml_sections(file_path: Path, source_name: str):
    """Stream a non-Jira XML file into per-top-level-child sections.

    Returns a list of ``_DocumentSection`` (imported lazily to avoid a
    circular import with ``services.ingest``). Same-tag children are
    grouped into chunks of up to 50 to keep section count bounded.
    Returns an empty list if the document has fewer than the minimum
    number of top-level children — caller falls back to single-note path.
    """
    from services.ingest import (
        _DocumentSection,
        SECTION_SPLIT_MIN_HEADINGS,
        SECTION_SPLIT_MAX_SECTIONS,
    )

    def _local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    try:
        context = ET.iterparse(str(file_path), events=("start", "end"))
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    grouped: Dict[str, List[str]] = {}
    root_tag: Optional[str] = None
    depth = 0
    total_children = 0

    for event, elem in context:
        if event == "start":
            if root_tag is None:
                root_tag = _local(elem.tag)
            depth += 1
            continue

        depth -= 1
        if depth == 1:
            tag = _local(elem.tag)
            try:
                serialized = ET.tostring(elem, encoding="unicode")
            except Exception:
                serialized = f"<{tag}/>"
            if len(serialized) > _XML_SECTION_TRUNCATE:
                serialized = serialized[:_XML_SECTION_TRUNCATE] + "\n<!-- truncated -->"
            grouped.setdefault(tag, []).append(serialized)
            total_children += 1
            elem.clear()
        elif depth == 0:
            elem.clear()
            break

    if total_children < SECTION_SPLIT_MIN_HEADINGS:
        return []

    chunk = 50
    sections: List["_DocumentSection"] = []
    for tag, items in grouped.items():
        if len(items) <= chunk:
            for idx, item in enumerate(items, start=1):
                title = f"{tag} {idx}" if len(items) > 1 else tag
                body = "```xml\n" + item + "\n```"
                sections.append(_DocumentSection(title=title, body=body))
        else:
            for start in range(0, len(items), chunk):
                end = min(start + chunk, len(items))
                joined = "\n\n".join(items[start:end])
                if len(joined) > _XML_SECTION_TRUNCATE:
                    joined = joined[:_XML_SECTION_TRUNCATE] + "\n<!-- truncated -->"
                title = f"{tag} {start + 1}–{end}"
                body = "```xml\n" + joined + "\n```"
                sections.append(_DocumentSection(title=title, body=body))

    if len(sections) > SECTION_SPLIT_MAX_SECTIONS:
        sections = sections[:SECTION_SPLIT_MAX_SECTIONS]

    return sections


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

async def ingest_structured_file(
    file_path: Path,
    target_folder: str = "knowledge",
    workspace_path: Optional[Path] = None,
    original_name: Optional[str] = None,
) -> Dict:
    """Ingest a CSV or XML file into Jarvis memory.

    For Jira exports: groups issues by epic/project, extracts entities,
    creates overview + detail notes.

    For generic CSV/XML: converts to readable markdown.

    Returns dict with paths of all created notes and extraction stats.
    """
    ws = workspace_path or get_settings().workspace_path
    mem = ws / "memory"
    folder = mem / target_folder
    folder.mkdir(parents=True, exist_ok=True)

    display_name = original_name or file_path.name
    ext = Path(display_name).suffix.lower()
    source_name = Path(display_name).stem

    created_notes: List[Dict] = []

    def _write_note(filename: str, content: str) -> Path:
        from services.ingest import _unique_path
        target = _unique_path(folder / filename)
        target.write_text(content, encoding="utf-8")
        return target

    if ext == ".csv":
        headers, issues, is_jira = parse_csv_file(file_path)
        if is_jira and issues:
            created_notes = await _ingest_jira_issues(
                issues, source_name, folder, mem, _write_note, workspace_path
            )
        elif headers:
            filename, content = _build_generic_csv_note(file_path, headers, source_name)
            if content:
                target = _write_note(filename, content)
                rel_path = target.relative_to(mem).as_posix()
                await _index_note(rel_path, workspace_path)
                created_notes.append({"path": rel_path, "title": f"CSV: {source_name}"})
        else:
            raise ValueError("Empty CSV file")

    elif ext == ".xml":
        issues, is_jira = parse_xml_file(file_path)
        if is_jira and issues:
            created_notes = await _ingest_jira_issues(
                issues, source_name, folder, mem, _write_note, workspace_path
            )
        else:
            # Step 27d — large generic XML files get split into per-top-level
            # child sections so the graph sees a cluster of related notes
            # rather than one mega-note.
            from services.ingest import (
                SECTION_SPLIT_MIN_CHARS,
                SECTION_SPLIT_MIN_HEADINGS,
                _emit_document_sections,
            )

            try:
                file_size = file_path.stat().st_size
            except OSError:
                file_size = 0

            xml_sections: List = []
            if file_size >= SECTION_SPLIT_MIN_CHARS:
                try:
                    xml_sections = _build_xml_sections(file_path, source_name)
                except ValueError as exc:
                    logger.warning("XML section split skipped (%s): %s", file_path.name, exc)
                    xml_sections = []

            if len(xml_sections) >= SECTION_SPLIT_MIN_HEADINGS:
                result = await _emit_document_sections(
                    doc_type="xml",
                    title=source_name,
                    source_path=file_path,
                    target_folder=target_folder,
                    workspace_path=workspace_path,
                    sections=xml_sections,
                    job_id=None,
                )
                # Skip the global rebuild_graph below — _emit_document_sections
                # already runs Smart Connect on the index note.
                return {
                    "notes": [{
                        "path": result["path"],
                        "title": result["title"],
                    }],
                    "total_notes": 1,
                    "sections": result.get("sections", len(xml_sections)),
                    "source": display_name,
                    "format": "generic",
                    "folder": target_folder,
                }

            filename, content = _build_generic_xml_note(file_path, source_name)
            target = _write_note(filename, content)
            rel_path = target.relative_to(mem).as_posix()
            await _index_note(rel_path, workspace_path)
            created_notes.append({"path": rel_path, "title": f"XML: {source_name}"})
    else:
        raise ValueError(f"Unsupported structured file type: {ext}")

    # Rebuild graph once after all notes are created
    try:
        from services.graph_service import rebuild_graph
        rebuild_graph(workspace_path=workspace_path)
    except Exception as exc:
        logger.warning("Graph rebuild after structured ingest failed: %s", exc)

    return {
        "notes": created_notes,
        "total_notes": len(created_notes),
        "source": display_name,
        "format": "jira" if any(n.get("type") == "jira" for n in created_notes) else "generic",
        "folder": target_folder,
    }


async def _ingest_jira_issues(
    issues: List[JiraIssue],
    source_name: str,
    folder: Path,
    mem: Path,
    write_fn,
    workspace_path: Optional[Path],
) -> List[Dict]:
    """Create grouped markdown notes from Jira issues."""
    created_notes: List[Dict] = []
    groups = _group_issues(issues)

    # 1. Overview note
    overview_content = _build_summary_note(issues, source_name, groups)
    overview_filename = f"jira-overview-{_slugify(source_name)}.md"
    target = write_fn(overview_filename, overview_content)
    rel_path = target.relative_to(mem).as_posix()
    await _index_note(rel_path, workspace_path)
    created_notes.append({
        "path": rel_path,
        "title": f"Jira Export Overview: {source_name}",
        "type": "jira",
        "issues": len(issues),
    })

    # 2. Group notes
    for group_name, group_issues in groups.items():
        note_parts = _build_group_note(group_name, group_issues, source_name)
        for filename, content in note_parts:
            target = write_fn(filename, content)
            rel_path = target.relative_to(mem).as_posix()
            await _index_note(rel_path, workspace_path)
            created_notes.append({
                "path": rel_path,
                "title": f"Jira: {group_name}",
                "type": "jira",
                "issues": len(group_issues),
            })

    return created_notes


async def _index_note(rel_path: str, workspace_path: Optional[Path]) -> None:
    """Index a single note in SQLite."""
    from services.memory_service import index_note_file
    try:
        await index_note_file(rel_path, workspace_path=workspace_path)
    except Exception as exc:
        logger.warning("Failed to index %s: %s", rel_path, exc)
