import json

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from services.session_service import (
    SessionNotFoundError,
    _sessions,
    add_message,
    create_session,
    delete_session,
    delete_session_file,
    get_messages,
    list_sessions,
    load_session,
    record_tool_use,
    resume_session,
    save_session,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def clean_sessions():
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "app" / "sessions").mkdir(parents=True)
    return tmp_path


def test_save_session_creates_file(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi there")
    save_session(sid, ws)
    assert (ws / "app" / "sessions" / f"{sid}.json").exists()


def test_save_session_skips_single_message(ws):
    """save_session requires at least 2 messages (a complete exchange)."""
    sid = create_session()
    add_message(sid, "user", "Hello")
    save_session(sid, ws)
    assert not (ws / "app" / "sessions" / f"{sid}.json").exists()


def test_save_session_has_metadata(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi there")
    save_session(sid, ws)
    data = json.loads((ws / "app" / "sessions" / f"{sid}.json").read_text())
    assert data["session_id"] == sid
    assert "created_at" in data
    assert data["message_count"] == 2
    assert data["title"] == "Hello"


def test_save_session_has_messages(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)
    data = json.loads((ws / "app" / "sessions" / f"{sid}.json").read_text())
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"


def test_save_session_auto_title(ws):
    sid = create_session()
    add_message(sid, "user", "Plan my week please")
    add_message(sid, "assistant", "Sure, here's a plan")
    save_session(sid, ws)
    data = json.loads((ws / "app" / "sessions" / f"{sid}.json").read_text())
    assert data["title"] == "Plan my week please"


async def test_list_sessions_sorted(ws):
    for i in range(3):
        sid = create_session()
        add_message(sid, "user", f"Message {i}")
        add_message(sid, "assistant", f"Reply {i}")
        save_session(sid, ws)
        delete_session(sid)

    sessions = await list_sessions(ws)
    assert len(sessions) == 3
    dates = [s["created_at"] for s in sessions]
    assert dates == sorted(dates, reverse=True)


async def test_list_sessions_metadata_only(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)

    sessions = await list_sessions(ws)
    assert len(sessions) == 1
    assert "messages" not in sessions[0]
    assert "session_id" in sessions[0]


async def test_list_sessions_empty(ws):
    sessions = await list_sessions(ws)
    assert sessions == []


def test_load_session_full(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)

    data = load_session(sid, ws)
    assert len(data["messages"]) == 2
    assert data["session_id"] == sid


def test_load_session_not_found(ws):
    with pytest.raises(SessionNotFoundError):
        load_session("nonexistent000", ws)


def test_resume_session_restores_history(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)
    delete_session(sid)

    resume_session(sid, ws)
    msgs = get_messages(sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"


def test_resume_session_appends_new(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)
    delete_session(sid)

    resume_session(sid, ws)
    add_message(sid, "user", "Follow up")
    msgs = get_messages(sid)
    assert len(msgs) == 3
    assert msgs[2]["content"] == "Follow up"


def test_delete_session_file(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)
    assert (ws / "app" / "sessions" / f"{sid}.json").exists()

    delete_session_file(sid, ws)
    assert not (ws / "app" / "sessions" / f"{sid}.json").exists()


def test_session_file_valid_json(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi")
    save_session(sid, ws)
    data = json.loads((ws / "app" / "sessions" / f"{sid}.json").read_text())
    assert isinstance(data, dict)


def test_concurrent_sessions_isolated(ws):
    sid1 = create_session()
    sid2 = create_session()
    add_message(sid1, "user", "Session 1")
    add_message(sid2, "user", "Session 2")

    msgs1 = get_messages(sid1)
    msgs2 = get_messages(sid2)
    assert len(msgs1) == 1
    assert len(msgs2) == 1
    assert msgs1[0]["content"] == "Session 1"
    assert msgs2[0]["content"] == "Session 2"


def test_record_tool_use(ws):
    sid = create_session()
    record_tool_use(sid, "search_notes")
    record_tool_use(sid, "create_plan")
    record_tool_use(sid, "search_notes")  # duplicate
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Found your notes")
    save_session(sid, ws)
    data = json.loads((ws / "app" / "sessions" / f"{sid}.json").read_text())
    assert sorted(data["tools_used"]) == ["create_plan", "search_notes"]
