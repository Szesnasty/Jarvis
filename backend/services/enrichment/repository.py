"""SQLite storage and queue operations for enrichment."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite
import logging

from models.database import init_database

from .models import PROMPT_VERSION, QueueItem, SUBJECT_JIRA, SUBJECT_NOTE
from .runtime import db_path, select_model_id, utc_now, workspace
from .subjects import allowed_note_path, resolve_content_hash

logger = logging.getLogger(__name__)


def _sanitize_for_log(value: object) -> str:
    """Return a single-line representation safe for plain-text logs."""
    return str(value).replace("\r", "").replace("\n", "")


QUEUE_MAX_ITEMS = 10000


async def upsert_enrichment(
    db: aiosqlite.Connection,
    *,
    subject_type: str,
    subject_id: str,
    content_hash: str,
    model_id: str,
    status: str,
    payload: dict[str, Any],
    raw_output: Optional[str],
    tokens_in: Optional[int],
    tokens_out: Optional[int],
    duration_ms: Optional[int],
) -> None:
    now = utc_now()
    await db.execute(
        """
        INSERT INTO enrichments(
            subject_type, subject_id, content_hash, model_id, prompt_version,
            status, payload, raw_output, tokens_in, tokens_out, duration_ms, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(subject_type, subject_id, content_hash, model_id, prompt_version)
        DO UPDATE SET
            status=excluded.status,
            payload=excluded.payload,
            raw_output=excluded.raw_output,
            tokens_in=excluded.tokens_in,
            tokens_out=excluded.tokens_out,
            duration_ms=excluded.duration_ms,
            created_at=excluded.created_at
        """,
        (
            subject_type,
            subject_id,
            content_hash,
            model_id,
            PROMPT_VERSION,
            status,
            json.dumps(payload, ensure_ascii=False),
            raw_output,
            tokens_in,
            tokens_out,
            duration_ms,
            now,
        ),
    )


async def cache_hit_exists(
    db: aiosqlite.Connection,
    *,
    subject_type: str,
    subject_id: str,
    content_hash: str,
    model_id: str,
) -> bool:
    row = await (
        await db.execute(
            """
            SELECT 1
            FROM enrichments
            WHERE subject_type = ? AND subject_id = ?
              AND content_hash = ? AND model_id = ?
              AND prompt_version = ? AND status = 'ok'
            LIMIT 1
            """,
            (subject_type, subject_id, content_hash, model_id, PROMPT_VERSION),
        )
    ).fetchone()
    return row is not None


async def enqueue_item(
    subject_type: str,
    subject_id: str,
    content_hash: str,
    *,
    reason: str = "manual",
    workspace_path: Optional[Path] = None,
    db: Optional[aiosqlite.Connection] = None,
) -> None:
    now = utc_now()

    async def _write(target_db: aiosqlite.Connection) -> None:
        existing = await (
            await target_db.execute(
                """
                SELECT 1 FROM enrichment_queue
                WHERE subject_type = ? AND subject_id = ? AND content_hash = ?
                LIMIT 1
                """,
                (subject_type, subject_id, content_hash),
            )
        ).fetchone()

        if existing is None:
            queued_count = await (
                await target_db.execute(
                    "SELECT COUNT(1) FROM enrichment_queue WHERE status IN ('pending','processing')"
                )
            ).fetchone()
            if int(queued_count[0]) >= QUEUE_MAX_ITEMS:
                logger.warning(
                    "Enrichment queue capacity reached (%d); dropping enqueue for %s/%s",
                    QUEUE_MAX_ITEMS,
                    _sanitize_for_log(subject_type),
                    _sanitize_for_log(subject_id),
                )
                return

        await target_db.execute(
            """
            INSERT INTO enrichment_queue(
                subject_type, subject_id, content_hash, reason, created_at, status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(subject_type, subject_id, content_hash)
            DO UPDATE SET
                reason=excluded.reason,
                created_at=excluded.created_at,
                status='pending',
                started_at=NULL
            """,
            (subject_type, subject_id, content_hash, reason, now),
        )

    if db is not None:
        await _write(db)
        return

    target = db_path(workspace_path)
    await init_database(target)
    async with aiosqlite.connect(str(target)) as own_db:
        await _write(own_db)
        await own_db.commit()


async def enqueue_jira_issue(
    issue_key: str,
    content_hash: str,
    *,
    reason: str = "jira_import",
    workspace_path: Optional[Path] = None,
    db: Optional[aiosqlite.Connection] = None,
) -> None:
    await enqueue_item(
        SUBJECT_JIRA,
        issue_key,
        content_hash,
        reason=reason,
        workspace_path=workspace_path,
        db=db,
    )


async def claim_next_item(db: aiosqlite.Connection) -> Optional[QueueItem]:
    await db.execute("BEGIN IMMEDIATE")
    row = await (
        await db.execute(
            """
            SELECT id, subject_type, subject_id, content_hash
            FROM enrichment_queue
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
            """
        )
    ).fetchone()
    if row is None:
        await db.commit()
        return None

    await db.execute(
        "UPDATE enrichment_queue SET status='processing', started_at=? WHERE id = ?",
        (utc_now(), row[0]),
    )
    await db.commit()
    return QueueItem(id=row[0], subject_type=row[1], subject_id=row[2], content_hash=row[3])


async def mark_item_done(db: aiosqlite.Connection, item_id: int) -> None:
    await db.execute("DELETE FROM enrichment_queue WHERE id = ?", (item_id,))
    await db.commit()


async def mark_item_failed(db: aiosqlite.Connection, item_id: int) -> None:
    await db.execute("UPDATE enrichment_queue SET status='failed' WHERE id = ?", (item_id,))
    await db.commit()


async def queue_status(workspace_path: Optional[Path] = None) -> dict[str, Any]:
    target = db_path(workspace_path)
    await init_database(target)

    failed_cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with aiosqlite.connect(str(target)) as db:
        pending = (await (await db.execute(
            "SELECT COUNT(1) FROM enrichment_queue WHERE status='pending'"
        )).fetchone())[0]
        processing = (await (await db.execute(
            "SELECT COUNT(1) FROM enrichment_queue WHERE status='processing'"
        )).fetchone())[0]
        failed_last_hour = (await (await db.execute(
            "SELECT COUNT(1) FROM enrichments WHERE status='failed' AND created_at >= ?",
            (failed_cutoff,),
        )).fetchone())[0]
        completed_total = (await (await db.execute(
            "SELECT COUNT(1) FROM enrichments WHERE status='ok'"
        )).fetchone())[0]

    return {
        "pending": int(pending),
        "processing": int(processing),
        "failed_last_hour": int(failed_last_hour),
        "completed_total": int(completed_total),
        "model_id": select_model_id(workspace_path),
    }


async def cancel_queue(*, workspace_path: Optional[Path] = None) -> int:
    """Delete all pending items from the enrichment queue. Returns count removed."""
    target = db_path(workspace_path)
    await init_database(target)

    async with aiosqlite.connect(str(target)) as db:
        cursor = await db.execute(
            "DELETE FROM enrichment_queue WHERE status='pending'"
        )
        removed = cursor.rowcount
        await db.commit()
    return removed


async def get_latest_enrichment(
    subject_type: str,
    subject_id: str,
    *,
    workspace_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    target = db_path(workspace_path)
    await init_database(target)

    async with aiosqlite.connect(str(target)) as db:
        db.row_factory = aiosqlite.Row
        row = await (
            await db.execute(
                """
                SELECT payload, model_id, prompt_version, created_at
                FROM latest_enrichment
                WHERE subject_type = ? AND subject_id = ?
                LIMIT 1
                """,
                (subject_type, subject_id),
            )
        ).fetchone()

    if not row:
        return None

    payload = {}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}

    return {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "model_id": row["model_id"],
        "prompt_version": int(row["prompt_version"]),
        "created_at": row["created_at"],
        "payload": payload,
    }


async def rerun(
    *,
    reason: str,
    subject_type: Optional[str] = None,
    subject_ids: Optional[list[str]] = None,
    workspace_path: Optional[Path] = None,
) -> int:
    ws = workspace(workspace_path)
    target = db_path(workspace_path)
    await init_database(target)

    queued = 0
    async with aiosqlite.connect(str(target)) as db:
        if subject_ids:
            if not subject_type:
                raise ValueError("subject_type is required when subject_ids are provided")
            for sid in subject_ids:
                content_hash = await resolve_content_hash(db, ws, subject_type, sid)
                if not content_hash:
                    continue
                await enqueue_item(
                    subject_type,
                    sid,
                    content_hash,
                    reason=reason,
                    db=db,
                    workspace_path=workspace_path,
                )
                queued += 1
        else:
            query = """
                SELECT DISTINCT subject_type, subject_id
                FROM enrichments
                WHERE status='failed'
            """
            params: list[Any] = []
            if subject_type:
                query += " AND subject_type = ?"
                params.append(subject_type)

            rows = await (await db.execute(query, params)).fetchall()
            for st, sid in rows:
                content_hash = await resolve_content_hash(db, ws, st, sid)
                if not content_hash:
                    continue
                await enqueue_item(
                    st,
                    sid,
                    content_hash,
                    reason=reason,
                    db=db,
                    workspace_path=workspace_path,
                )
                queued += 1

        await db.commit()

    return queued


async def sharpen_all(
    *,
    reason: str = "manual_sharpen_all",
    include_notes: bool = True,
    include_jira: bool = True,
    workspace_path: Optional[Path] = None,
) -> dict[str, int]:
    """Enqueue every eligible note and Jira issue for local-AI enrichment.

    Walks the memory/ folder for *.md files (filtered by allowed_note_path)
    and pulls all known Jira issues. Existing successful enrichments with the
    same content_hash + model + prompt are skipped silently inside the worker
    via cache_hit_exists, so re-running is cheap.
    """
    ws = workspace(workspace_path)
    target = db_path(workspace_path)
    await init_database(target)

    queued_notes = 0
    queued_jira = 0
    skipped = 0

    async with aiosqlite.connect(str(target)) as db:
        if include_notes:
            mem = ws / "memory"
            if mem.exists():
                for md_file in sorted(mem.rglob("*.md")):
                    try:
                        rel = md_file.relative_to(ws).as_posix()
                    except ValueError:
                        continue
                    if not allowed_note_path(rel):
                        skipped += 1
                        continue
                    content_hash = await resolve_content_hash(
                        db, ws, SUBJECT_NOTE, rel
                    )
                    if not content_hash:
                        skipped += 1
                        continue
                    await enqueue_item(
                        SUBJECT_NOTE,
                        rel,
                        content_hash,
                        reason=reason,
                        db=db,
                        workspace_path=workspace_path,
                    )
                    queued_notes += 1

        if include_jira:
            rows = await (
                await db.execute(
                    "SELECT issue_key, content_hash FROM issues"
                )
            ).fetchall()
            for issue_key, content_hash in rows:
                if not content_hash:
                    skipped += 1
                    continue
                await enqueue_item(
                    SUBJECT_JIRA,
                    str(issue_key),
                    str(content_hash),
                    reason=reason,
                    db=db,
                    workspace_path=workspace_path,
                )
                queued_jira += 1

        await db.commit()

    logger.info(
        "sharpen_all enqueued notes=%d jira=%d skipped=%d (reason=%s)",
        queued_notes,
        queued_jira,
        skipped,
        reason,
    )
    return {
        "queued_notes": queued_notes,
        "queued_jira": queued_jira,
        "queued": queued_notes + queued_jira,
        "skipped": skipped,
        "model_id": select_model_id(workspace_path),
    }
