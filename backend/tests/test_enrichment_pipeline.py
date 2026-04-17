"""Tests for step 22c enrichment pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from models.database import init_database
from services.enrichment.models import SUBJECT_JIRA
from services.enrichment.repository import (
    cache_hit_exists,
    enqueue_jira_issue,
    get_latest_enrichment,
)
from services.enrichment.worker import process_item

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


async def _seed_issue(db: aiosqlite.Connection, *, key: str, project: str, content_hash: str) -> None:
    await db.execute(
        """
        INSERT INTO issues(
            issue_key, project_key, title, description, issue_type,
            status, status_category, created_at, updated_at,
            note_path, content_hash, imported_at
        ) VALUES(?, ?, ?, ?, 'Task', 'Open', 'to-do', ?, ?, ?, ?, ?)
        """,
        (
            key,
            project,
            f"Title {key}",
            "Short description",
            "2026-04-17T00:00:00Z",
            "2026-04-17T00:00:00Z",
            f"memory/jira/{project}/{key}.md",
            content_hash,
            "2026-04-17T00:00:00Z",
        ),
    )


async def test_enrichment_schema_enforced(ws: Path):
    db_path = ws / "app" / "jarvis.db"
    await init_database(db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        await _seed_issue(db, key="ONB-1", project="ONB", content_hash="h1")
        await enqueue_jira_issue("ONB-1", "h1", workspace_path=ws, db=db)
        item = await (await db.execute(
            "SELECT id, subject_type, subject_id, content_hash FROM enrichment_queue LIMIT 1"
        )).fetchone()
        await db.commit()

    queue_item = type("Q", (), {"id": item[0], "subject_type": item[1], "subject_id": item[2], "content_hash": item[3]})

    with patch("services.enrichment.worker.select_model_id", return_value="ollama_chat/qwen3:4b"), patch(
        "services.enrichment.worker.call_local_model",
        new=AsyncMock(return_value=("{not-json", 10, 5, 100)),
    ):
        async with aiosqlite.connect(str(db_path)) as db:
            await process_item(db, queue_item, workspace_path=ws)
            row = await (await db.execute(
                "SELECT status, payload, raw_output FROM enrichments WHERE subject_type=? AND subject_id=?",
                (SUBJECT_JIRA, "ONB-1"),
            )).fetchone()

    assert row is not None
    assert row[0] == "failed"
    assert row[1] == "{}"
    assert row[2]


async def test_cache_hit_no_model_call(ws: Path):
    db_path = ws / "app" / "jarvis.db"
    await init_database(db_path)

    model_id = "ollama_chat/qwen3:4b"

    async with aiosqlite.connect(str(db_path)) as db:
        await _seed_issue(db, key="ONB-2", project="ONB", content_hash="h2")
        await db.execute(
            """
            INSERT INTO enrichments(
                subject_type, subject_id, content_hash, model_id, prompt_version,
                status, payload, created_at
            ) VALUES(?, ?, ?, ?, 1, 'ok', ?, '2026-04-17T00:00:00Z')
            """,
            (SUBJECT_JIRA, "ONB-2", "h2", model_id, '{"summary":"ok","actionable_next_step":"x","work_type":"feature","business_area":"unknown","execution_type":"implementation","risk_level":"low","ambiguity_level":"clear","hidden_concerns":[],"likely_related_issue_keys":[],"likely_related_note_paths":[],"keywords":["one","two","three"]}'),
        )
        await db.commit()

        hit = await cache_hit_exists(
            db,
            subject_type=SUBJECT_JIRA,
            subject_id="ONB-2",
            content_hash="h2",
            model_id=model_id,
        )
    assert hit is True


async def test_prompt_version_invalidates(ws: Path):
    db_path = ws / "app" / "jarvis.db"
    await init_database(db_path)

    model_id = "ollama_chat/qwen3:4b"

    async with aiosqlite.connect(str(db_path)) as db:
        await _seed_issue(db, key="ONB-3", project="ONB", content_hash="h3")
        await db.execute(
            """
            INSERT INTO enrichments(
                subject_type, subject_id, content_hash, model_id, prompt_version,
                status, payload, created_at
            ) VALUES(?, ?, ?, ?, 999, 'ok', ?, '2026-04-17T00:00:00Z')
            """,
            (SUBJECT_JIRA, "ONB-3", "h3", model_id, '{"summary":"ok","actionable_next_step":"x","work_type":"feature","business_area":"unknown","execution_type":"implementation","risk_level":"low","ambiguity_level":"clear","hidden_concerns":[],"likely_related_issue_keys":[],"likely_related_note_paths":[],"keywords":["one","two","three"]}'),
        )
        await db.commit()

        hit = await cache_hit_exists(
            db,
            subject_type=SUBJECT_JIRA,
            subject_id="ONB-3",
            content_hash="h3",
            model_id=model_id,
        )
    assert hit is False


async def test_enum_mapping_and_hallucinated_keys_filtered(ws: Path):
    db_path = ws / "app" / "jarvis.db"
    await init_database(db_path)

    async with aiosqlite.connect(str(db_path)) as db:
        await _seed_issue(db, key="ONB-10", project="ONB", content_hash="h10")
        await _seed_issue(db, key="ONB-11", project="ONB", content_hash="h11")
        await enqueue_jira_issue("ONB-10", "h10", workspace_path=ws, db=db)
        item = await (await db.execute(
            "SELECT id, subject_type, subject_id, content_hash FROM enrichment_queue LIMIT 1"
        )).fetchone()
        await db.commit()

    queue_item = type("Q", (), {"id": item[0], "subject_type": item[1], "subject_id": item[2], "content_hash": item[3]})

    raw = """
    {
      "summary": "A",
      "actionable_next_step": "B",
      "work_type": "SOMETHING_ELSE",
      "business_area": "NON_EXISTENT",
      "execution_type": "??",
      "risk_level": "CRITICAL",
      "ambiguity_level": "MAYBE",
      "hidden_concerns": ["c1"],
      "likely_related_issue_keys": ["ONB-11", "FOO-999"],
      "keywords": ["k1", "k2", "k3"]
    }
    """

    with patch("services.enrichment.worker.select_model_id", return_value="ollama_chat/qwen3:4b"), patch(
        "services.enrichment.worker.call_local_model",
        new=AsyncMock(return_value=(raw, 10, 5, 100)),
    ):
        async with aiosqlite.connect(str(db_path)) as db:
            await process_item(db, queue_item, workspace_path=ws)

    result = await get_latest_enrichment(SUBJECT_JIRA, "ONB-10", workspace_path=ws)
    assert result is not None
    payload = result["payload"]
    assert payload["work_type"] == "unknown"
    assert payload["business_area"] == "unknown"
    assert payload["execution_type"] == "unknown"
    assert payload["risk_level"] == "medium"
    assert payload["ambiguity_level"] == "partial"
    assert payload["likely_related_issue_keys"] == ["ONB-11"]
