"""Subject loading and prompt construction for enrichment."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from .models import SUBJECT_JIRA, SUBJECT_NOTE
from .runtime import load_prompt_template, workspace


def extract_json_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "{}"

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        return text[first:last + 1]
    return text


def truncate(text: str, limit: int) -> str:
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)].rstrip() + "..."


def fallback_keywords(*parts: str) -> list[str]:
    import re

    tokens: list[str] = []
    for part in parts:
        for token in re.findall(r"[A-Za-z0-9_\-/]{3,}", part or ""):
            t = token.lower()
            if t not in tokens:
                tokens.append(t)
            if len(tokens) >= 8:
                break
        if len(tokens) >= 8:
            break
    while len(tokens) < 3:
        tokens.append(["task", "jira", "work"][len(tokens)])
    return tokens[:8]


def allowed_note_path(subject_id: str) -> bool:
    s = subject_id.replace("\\", "/")
    return s.startswith("memory/projects/") or s.startswith("memory/decisions/")


async def load_subject_context(
    db: aiosqlite.Connection,
    *,
    subject_type: str,
    subject_id: str,
    workspace_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    if subject_type == SUBJECT_JIRA:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT issue_key, project_key, title, description, content_hash
            FROM issues WHERE issue_key = ?
            """,
            (subject_id,),
        )
        issue = await cursor.fetchone()
        if not issue:
            return None

        comment_rows = await (
            await db.execute(
                """
                SELECT body FROM issue_comments
                WHERE issue_key = ?
                ORDER BY id ASC
                LIMIT 6
                """,
                (subject_id,),
            )
        ).fetchall()
        comments = [str(r[0] or "") for r in comment_rows]

        whitelist_rows = await (
            await db.execute(
                """
                SELECT issue_key FROM issues
                WHERE project_key = ?
                ORDER BY updated_at DESC
                LIMIT 80
                """,
                (issue["project_key"],),
            )
        ).fetchall()
        whitelist = [str(r[0]) for r in whitelist_rows]

        text_parts = [
            f"Title: {issue['title']}",
            "Description:",
            str(issue["description"] or ""),
        ]
        if comments:
            text_parts.append("Comments:")
            for idx, body in enumerate(comments, start=1):
                text_parts.append(f"- C{idx}: {body}")

        content = "\n".join(text_parts)
        content = truncate(content, 7000)

        return {
            "subject_type": SUBJECT_JIRA,
            "subject_id": subject_id,
            "content_hash": str(issue["content_hash"]),
            "title": str(issue["title"] or ""),
            "content": content,
            "project_key": str(issue["project_key"] or ""),
            "issue_key_whitelist": whitelist,
        }

    if subject_type == SUBJECT_NOTE:
        if not allowed_note_path(subject_id):
            return None
        ws = workspace(workspace_path)
        note_path = ws / subject_id
        try:
            resolved = note_path.resolve()
            ws_resolved = ws.resolve()
            if ws_resolved not in resolved.parents and resolved != ws_resolved:
                return None
        except OSError:
            return None

        if not note_path.exists() or not note_path.is_file():
            return None

        try:
            note_text = note_path.read_text(encoding="utf-8")
        except OSError:
            return None

        note_text = truncate(note_text, 7000)
        content_hash = hashlib.sha256(note_text.encode("utf-8")).hexdigest()

        return {
            "subject_type": SUBJECT_NOTE,
            "subject_id": subject_id,
            "content_hash": content_hash,
            "title": note_path.stem,
            "content": note_text,
            "project_key": "",
            "issue_key_whitelist": [],
        }

    return None


def build_prompt(context: dict[str, Any], business_areas: list[str]) -> str:
    if context["subject_type"] == SUBJECT_JIRA:
        template = load_prompt_template("jira_issue_v1.txt")
        return (
            template.replace("{{BUSINESS_AREAS}}", ", ".join(business_areas))
            .replace(
                "{{ISSUE_KEY_WHITELIST}}",
                ", ".join(context.get("issue_key_whitelist") or []) or "(empty)",
            )
            .replace("{{ISSUE_CONTENT}}", context.get("content") or "")
        )

    template = load_prompt_template("note_v1.txt")
    return (
        template.replace("{{BUSINESS_AREAS}}", ", ".join(business_areas))
        .replace("{{NOTE_PATH}}", context.get("subject_id") or "")
        .replace("{{NOTE_CONTENT}}", context.get("content") or "")
    )


async def resolve_content_hash(
    db: aiosqlite.Connection,
    workspace_path: Path,
    subject_type: str,
    subject_id: str,
) -> Optional[str]:
    if subject_type == SUBJECT_JIRA:
        row = await (
            await db.execute(
                "SELECT content_hash FROM issues WHERE issue_key = ? LIMIT 1",
                (subject_id,),
            )
        ).fetchone()
        return str(row[0]) if row else None

    if subject_type == SUBJECT_NOTE and allowed_note_path(subject_id):
        note_path = workspace_path / subject_id
        if not note_path.exists() or not note_path.is_file():
            return None
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            return None
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    return None
