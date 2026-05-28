"""Step 30b — rolling conversation summary tests."""
import asyncio

import pytest

from services import session_service
from services.conversation_summary import (
    FOLD_BATCH,
    RECENT_WINDOW,
    fold_messages_into_summary,
    mechanical_summary,
)


@pytest.fixture
def session(tmp_path, monkeypatch):
    # Isolate session storage in tmp_path.
    from config import get_settings

    monkeypatch.setattr(
        get_settings(), "workspace_path", tmp_path, raising=False
    )
    sid = session_service.create_session()
    yield sid
    session_service.delete_session(sid)


def _seed(sid: str, count: int) -> None:
    for i in range(count):
        session_service.add_message(sid, "user", f"user message {i}")
        session_service.add_message(sid, "assistant", f"assistant reply {i}")


def test_recent_window_returns_full_history_when_short(session):
    _seed(session, 3)  # 6 messages, below window
    recent = session_service.get_recent_window(session, RECENT_WINDOW)
    assert len(recent) == 6
    assert all("role" in m and "content" in m for m in recent)


def test_recent_window_trims_when_overflow(session):
    _seed(session, 20)  # 40 messages, well over window
    recent = session_service.get_recent_window(session, RECENT_WINDOW)
    assert len(recent) == RECENT_WINDOW
    # Latest messages preserved
    assert recent[-1]["content"] == "assistant reply 19"


def test_pending_batch_empty_under_window(session):
    _seed(session, 3)  # 6 messages
    batch = session_service.pending_summary_batch(session, window=RECENT_WINDOW, batch=FOLD_BATCH)
    assert batch == []


def test_pending_batch_returns_oldest_outside_window(session):
    _seed(session, 12)  # 24 messages → 8 fall outside window of 16
    batch = session_service.pending_summary_batch(session, window=RECENT_WINDOW, batch=FOLD_BATCH)
    assert len(batch) == FOLD_BATCH
    # Oldest first
    assert batch[0]["content"] == "user message 0"


def test_apply_summary_advances_cursor(session):
    _seed(session, 12)
    batch = session_service.pending_summary_batch(session, window=RECENT_WINDOW, batch=FOLD_BATCH)
    session_service.apply_summary_update(session, "- topic A discussed", advanced_by=len(batch))
    # Next batch should start where we left off
    next_batch = session_service.pending_summary_batch(session, window=RECENT_WINDOW, batch=FOLD_BATCH)
    assert next_batch and next_batch[0]["content"] != batch[0]["content"]
    assert session_service.get_summary(session) == "- topic A discussed"


def test_mechanical_summary_keeps_topics():
    out = mechanical_summary(
        "",
        [
            {"role": "user", "content": "How is Adam doing on the Q3 plan?"},
            {"role": "assistant", "content": "Adam is on track, deadline Aug 15."},
        ],
    )
    assert "Adam" in out
    assert out.startswith("- ")


def test_mechanical_summary_caps_at_ten_entries():
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"line {i}"} for i in range(40)]
    out = mechanical_summary("", msgs)
    assert out.count("\n") <= 9  # 10 lines = 9 newlines


def test_fold_uses_mechanical_for_ollama():
    async def run():
        return await fold_messages_into_summary(
            "",
            [
                {"role": "user", "content": "co planujemy na piatek"},
                {"role": "assistant", "content": "Spotkanie z Adamem o 10:00."},
            ],
            provider="ollama",
            model="qwen3:8b",
            api_key="",
        )

    out = asyncio.run(run())
    assert "Adam" in out


def test_fold_uses_mechanical_when_no_api_key():
    async def run():
        return await fold_messages_into_summary(
            "",
            [{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-sonnet-4",
            api_key="",
        )

    out = asyncio.run(run())
    assert "hello" in out


def test_fold_failure_returns_existing_summary(monkeypatch):
    """LLM raises → existing summary preserved, no exception."""
    async def boom(*_args, **_kw):
        raise RuntimeError("provider down")

    from services import conversation_summary
    monkeypatch.setattr(conversation_summary, "_llm_fold", boom)

    async def run():
        return await fold_messages_into_summary(
            "- previous summary",
            [{"role": "user", "content": "new message"}],
            provider="anthropic",
            model="claude-sonnet-4",
            api_key="sk-test",
        )

    out = asyncio.run(run())
    assert out == "- previous summary"


def test_summary_persists_across_save_and_resume(tmp_path, monkeypatch):
    from config import get_settings

    monkeypatch.setattr(get_settings(), "workspace_path", tmp_path, raising=False)
    sid = session_service.create_session()
    try:
        _seed(sid, 5)
        session_service.apply_summary_update(sid, "- earlier conv summary", advanced_by=2)
        session_service.save_session(sid, workspace_path=tmp_path)
        session_service.delete_session(sid)
        session_service.resume_session(sid, workspace_path=tmp_path)
        assert session_service.get_summary(sid) == "- earlier conv summary"
    finally:
        session_service.delete_session(sid)
