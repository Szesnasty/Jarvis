"""Enrichment worker loop and model processing."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

import aiosqlite
import httpx
import sqlite3
from pydantic import ValidationError

from models.database import init_database
from services._db import apply_pragmas

from .models import (
    AMBIGUITY_LEVELS,
    EXECUTION_TYPES,
    PROMPT_VERSION,
    QUEUE_POLL_SLEEP_S,
    RISK_LEVELS,
    SUBJECT_JIRA,
    SUBJECT_NOTE,
    WORK_TYPES,
    DEFAULT_WORKER_CONCURRENCY,
    EnrichmentPayload,
    coerce_enum,
)
from .repository import (
    cache_hit_exists,
    claim_next_item,
    mark_item_done,
    mark_item_failed,
    upsert_enrichment,
)
from .runtime import (
    db_path,
    is_enrichment_enabled,
    is_on_battery_power,
    load_business_areas,
    select_base_url,
    select_model_id,
    should_pause_for_battery,
)
from .subjects import allowed_note_path, build_prompt, extract_json_text, fallback_keywords, load_subject_context

logger = logging.getLogger(__name__)

_worker_tasks: list[asyncio.Task] = []
_worker_running = False


async def call_local_model(
    *,
    model_id: str,
    prompt: str,
    temperature: float,
    workspace_path: Optional[Path] = None,
) -> tuple[str, int, int, int]:
    base_url = select_base_url(workspace_path)
    model_name = model_id.replace("ollama_chat/", "", 1)

    payload = {
        "model": model_name,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": float(temperature),
        },
        "messages": [
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    message = data.get("message") or {}
    text = str(message.get("content") or "")
    tokens_in = int(data.get("prompt_eval_count") or 0)
    tokens_out = int(data.get("eval_count") or 0)
    duration_ms = int((data.get("total_duration") or 0) / 1_000_000)

    return text, tokens_in, tokens_out, duration_ms


def normalize_payload(
    raw_payload: dict[str, Any],
    *,
    subject_type: str,
    business_areas: list[str],
    issue_key_whitelist: list[str],
    subject_id: str,
) -> tuple[dict[str, Any], int]:
    enum_remaps = 0

    work_type, changed = coerce_enum(raw_payload.get("work_type"), WORK_TYPES)
    enum_remaps += int(changed)

    execution_type, changed = coerce_enum(raw_payload.get("execution_type"), EXECUTION_TYPES)
    enum_remaps += int(changed)

    risk_level, changed = coerce_enum(raw_payload.get("risk_level"), RISK_LEVELS, "medium")
    enum_remaps += int(changed)

    ambiguity_level, changed = coerce_enum(
        raw_payload.get("ambiguity_level"), AMBIGUITY_LEVELS, "partial"
    )
    enum_remaps += int(changed)

    ba_allowed = set(business_areas)
    business_area, changed = coerce_enum(raw_payload.get("business_area"), ba_allowed)
    enum_remaps += int(changed)

    summary = str(raw_payload.get("summary") or "").strip()
    actionable = str(raw_payload.get("actionable_next_step") or "").strip()
    if not summary:
        summary = f"No summary generated for {subject_id}"
    if not actionable:
        actionable = "Clarify scope and define the next concrete action."

    concerns_raw = raw_payload.get("hidden_concerns")
    concerns: list[str] = []
    if isinstance(concerns_raw, list):
        concerns = [str(x).strip() for x in concerns_raw if str(x).strip()]

    keywords_raw = raw_payload.get("keywords")
    keywords: list[str] = []
    if isinstance(keywords_raw, list):
        keywords = [str(x).strip().lower() for x in keywords_raw if str(x).strip()]
    if len(keywords) < 3:
        keywords = fallback_keywords(summary, actionable)

    issue_keys: list[str] = []
    if subject_type == SUBJECT_JIRA:
        whitelist_set = set(issue_key_whitelist)
        raw_keys = raw_payload.get("likely_related_issue_keys")
        if isinstance(raw_keys, list):
            for key in raw_keys:
                k = str(key).strip().upper()
                if k in whitelist_set and k not in issue_keys:
                    issue_keys.append(k)

    related_notes: list[str] = []
    if subject_type == SUBJECT_NOTE:
        raw_paths = raw_payload.get("likely_related_note_paths")
        if isinstance(raw_paths, list):
            for p in raw_paths:
                s = str(p).strip().replace("\\", "/")
                if s and allowed_note_path(s) and s not in related_notes:
                    related_notes.append(s)

    normalized = {
        "summary": summary,
        "actionable_next_step": actionable,
        "work_type": work_type,
        "business_area": business_area,
        "execution_type": execution_type,
        "risk_level": risk_level,
        "ambiguity_level": ambiguity_level,
        "hidden_concerns": concerns,
        "likely_related_issue_keys": issue_keys,
        "likely_related_note_paths": related_notes,
        "keywords": keywords,
    }
    return normalized, enum_remaps


def parse_and_validate_payload(
    raw_text: str,
    *,
    subject_type: str,
    business_areas: list[str],
    issue_key_whitelist: list[str],
    subject_id: str,
) -> tuple[dict[str, Any], int]:
    json_text = extract_json_text(raw_text)
    payload = json.loads(json_text)
    if not isinstance(payload, dict):
        raise ValueError("model output must be a JSON object")

    normalized, remapped = normalize_payload(
        payload,
        subject_type=subject_type,
        business_areas=business_areas,
        issue_key_whitelist=issue_key_whitelist,
        subject_id=subject_id,
    )
    validated = EnrichmentPayload.model_validate(normalized)
    return validated.model_dump(), remapped


async def process_item(
    db: aiosqlite.Connection,
    item,
    *,
    workspace_path: Optional[Path] = None,
) -> None:
    model_id = select_model_id(workspace_path)

    if await cache_hit_exists(
        db,
        subject_type=item.subject_type,
        subject_id=item.subject_id,
        content_hash=item.content_hash,
        model_id=model_id,
    ):
        return

    context = await load_subject_context(
        db,
        subject_type=item.subject_type,
        subject_id=item.subject_id,
        workspace_path=workspace_path,
    )
    if context is None:
        logger.info("Skipping enrichment for missing subject %s/%s", item.subject_type, item.subject_id)
        return

    if context["content_hash"] != item.content_hash:
        return

    business_areas = load_business_areas(workspace_path)
    prompt = build_prompt(context, business_areas)

    last_raw = ""
    last_tokens_in = None
    last_tokens_out = None
    last_duration = None

    for attempt, temp in enumerate((0.2, 0.0), start=1):
        try:
            raw, tokens_in, tokens_out, duration_ms = await call_local_model(
                model_id=model_id,
                prompt=prompt,
                temperature=temp,
                workspace_path=workspace_path,
            )
            payload, remapped = parse_and_validate_payload(
                raw,
                subject_type=item.subject_type,
                business_areas=business_areas,
                issue_key_whitelist=context.get("issue_key_whitelist") or [],
                subject_id=item.subject_id,
            )
            if remapped > 0:
                logger.info(
                    "Enrichment enum remaps=%d for %s/%s",
                    remapped,
                    item.subject_type,
                    item.subject_id,
                )

            await upsert_enrichment(
                db,
                subject_type=item.subject_type,
                subject_id=item.subject_id,
                content_hash=item.content_hash,
                model_id=model_id,
                status="ok",
                payload=payload,
                raw_output=None,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                duration_ms=duration_ms,
            )
            await db.commit()
            return
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_raw = locals().get("raw", "") or last_raw
            last_tokens_in = locals().get("tokens_in", last_tokens_in)
            last_tokens_out = locals().get("tokens_out", last_tokens_out)
            last_duration = locals().get("duration_ms", last_duration)
            logger.warning(
                "Enrichment parse/validation failed on attempt %d for %s/%s: %s",
                attempt,
                item.subject_type,
                item.subject_id,
                exc,
            )
        except Exception as exc:
            last_raw = locals().get("raw", "") or last_raw
            logger.warning(
                "Enrichment model call failed on attempt %d for %s/%s: %s",
                attempt,
                item.subject_type,
                item.subject_id,
                exc,
            )

    await upsert_enrichment(
        db,
        subject_type=item.subject_type,
        subject_id=item.subject_id,
        content_hash=item.content_hash,
        model_id=model_id,
        status="failed",
        payload={},
        raw_output=last_raw or "",
        tokens_in=last_tokens_in,
        tokens_out=last_tokens_out,
        duration_ms=last_duration,
    )
    await db.commit()


async def worker_loop(worker_idx: int, workspace_path: Optional[Path] = None) -> None:
    target = db_path(workspace_path)
    await init_database(target)

    # Outer loop: reopen the connection on fatal connection-level errors
    # (e.g. a workspace reset that swaps the DB file out from under us, or
    # an aiosqlite worker thread that died). Without this, the inner loop
    # would spam ``sqlite3.DatabaseError: file is not a database`` forever
    # because the broken connection is never replaced.
    while _worker_running:
        try:
            await _run_one_connection(worker_idx, target, workspace_path)
        except asyncio.CancelledError:
            raise
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as exc:
            if not _worker_running:
                break
            logger.warning(
                "Enrichment worker %d connection lost (%s); reconnecting in 3s",
                worker_idx, exc,
            )
            await asyncio.sleep(3.0)
        except Exception:
            if not _worker_running:
                break
            logger.exception("Enrichment worker %d crashed; reconnecting in 3s", worker_idx)
            await asyncio.sleep(3.0)


async def _run_one_connection(
    worker_idx: int,
    target: Path,
    workspace_path: Optional[Path],
) -> None:
    """Run the worker poll loop against a single aiosqlite connection.

    Raises ``sqlite3.DatabaseError`` / ``sqlite3.OperationalError`` to the
    caller so the outer loop can reconnect.
    """
    async with aiosqlite.connect(str(target)) as db:
        # Long busy_timeout + NORMAL fsync. Heavy ingest of large PDFs
        # (200 MB+ → thousands of chunk + embedding writes) holds bursty
        # write locks; without these the worker dies instantly with
        # 'database is locked'.
        await apply_pragmas(db)
        while _worker_running:
            try:
                if not is_enrichment_enabled(workspace_path):
                    # User hasn't opted in to local-AI processing yet.
                    # Sleep and retry — the worker will start processing as
                    # soon as the user enables Sharpen in Settings.
                    await asyncio.sleep(5.0)
                    continue

                if should_pause_for_battery(workspace_path):
                    await asyncio.sleep(5.0)
                    continue

                item = await claim_next_item(db)
                if item is None:
                    await asyncio.sleep(QUEUE_POLL_SLEEP_S)
                    continue

                try:
                    await process_item(db, item, workspace_path=workspace_path)
                    await mark_item_done(db, item.id)
                except Exception:
                    logger.exception("Enrichment worker %d failed queue item %s", worker_idx, item.id)
                    await mark_item_failed(db, item.id)
            except asyncio.CancelledError:
                raise
            except sqlite3.OperationalError as exc:
                # 'database is locked' under heavy bulk-write contention
                # (ingest of large PDFs). Back off quietly instead of
                # spamming a 60-line traceback every poll cycle.
                msg = str(exc).lower()
                if "locked" in msg or "busy" in msg:
                    logger.debug("Enrichment worker %d backing off — DB busy", worker_idx)
                    await asyncio.sleep(3.0)
                else:
                    # Real operational fault (disk full, malformed schema,
                    # connection torn down by reset). Bubble up so the
                    # outer loop reopens the connection.
                    raise
            except sqlite3.DatabaseError:
                # 'file is not a database' / corruption / connection died.
                # Bubble up so worker_loop reopens the connection.
                raise
            except Exception:
                logger.exception("Enrichment worker %d loop error", worker_idx)
                await asyncio.sleep(1.0)


async def start_workers(
    *,
    concurrency: int = DEFAULT_WORKER_CONCURRENCY,
    workspace_path: Optional[Path] = None,
) -> None:
    global _worker_running, _worker_tasks
    if _worker_running:
        return

    _worker_running = True
    _worker_tasks = []
    for idx in range(max(1, int(concurrency))):
        _worker_tasks.append(asyncio.create_task(worker_loop(idx, workspace_path=workspace_path)))


async def stop_workers() -> None:
    global _worker_running, _worker_tasks
    if not _worker_running:
        return

    _worker_running = False
    for task in _worker_tasks:
        task.cancel()
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks = []
