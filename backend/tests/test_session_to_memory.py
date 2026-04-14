import json

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from services.session_service import (
    _sessions,
    _extract_tags,
    _extract_topics,
    _generate_title,
    _format_conversation_body,
    add_message,
    create_session,
    delete_session,
    record_note_access,
    record_tool_use,
    save_session,
    save_session_to_memory,
)
from utils.markdown import parse_frontmatter


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
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "memory" / "conversations").mkdir(parents=True)
    (tmp_path / "graph").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# record_note_access
# ---------------------------------------------------------------------------

def test_record_note_access():
    sid = create_session()
    record_note_access(sid, "projects/jarvis.md")
    record_note_access(sid, "daily/2026-04-12.md")
    assert _sessions[sid]["notes_accessed"] == {
        "projects/jarvis.md",
        "daily/2026-04-12.md",
    }


def test_record_note_access_deduplicates():
    sid = create_session()
    record_note_access(sid, "projects/jarvis.md")
    record_note_access(sid, "projects/jarvis.md")
    assert len(_sessions[sid]["notes_accessed"]) == 1


def test_record_note_access_missing_session():
    # Should not raise
    record_note_access("nonexistent", "some/note.md")


# ---------------------------------------------------------------------------
# save_session persists notes_accessed
# ---------------------------------------------------------------------------

def test_save_session_includes_notes_accessed(ws):
    sid = create_session()
    add_message(sid, "user", "Hello")
    add_message(sid, "assistant", "Hi there")
    record_note_access(sid, "projects/jarvis.md")
    record_note_access(sid, "inbox/idea.md")
    save_session(sid, ws)
    data = json.loads((ws / "app" / "sessions" / f"{sid}.json").read_text())
    assert "notes_accessed" in data
    assert sorted(data["notes_accessed"]) == ["inbox/idea.md", "projects/jarvis.md"]


# ---------------------------------------------------------------------------
# _extract_tags
# ---------------------------------------------------------------------------

def test_extract_tags_from_tools():
    session = {"tools_used": {"search_notes", "create_plan"}}
    tags = _extract_tags(session)
    assert "conversation" in tags
    assert "research" in tags
    assert "planning" in tags


def test_extract_tags_always_has_conversation():
    session = {"tools_used": set()}
    tags = _extract_tags(session)
    assert tags == ["conversation"]


# ---------------------------------------------------------------------------
# _extract_topics
# ---------------------------------------------------------------------------

def test_extract_topics_from_messages():
    messages = [
        {"role": "user", "content": "Tell me about the Jarvis project architecture"},
        {"role": "assistant", "content": "The Jarvis project uses..."},
        {"role": "user", "content": "How does the memory service work in Jarvis?"},
    ]
    topics = _extract_topics(messages)
    assert len(topics) > 0
    assert "jarvis" in topics


def test_extract_topics_empty_messages():
    topics = _extract_topics([])
    assert topics == []


# ---------------------------------------------------------------------------
# _generate_title
# ---------------------------------------------------------------------------

def test_generate_title_from_first_user_message():
    messages = [
        {"role": "user", "content": "Plan my week please"},
        {"role": "assistant", "content": "Sure!"},
    ]
    assert _generate_title(messages) == "Plan my week please"


def test_generate_title_truncates_long():
    messages = [{"role": "user", "content": "A" * 200}]
    title = _generate_title(messages)
    assert len(title) <= 83  # 80 + "..."


def test_generate_title_fallback():
    messages = [{"role": "assistant", "content": "Hi"}]
    assert _generate_title(messages) == "Untitled conversation"


# ---------------------------------------------------------------------------
# _format_conversation_body
# ---------------------------------------------------------------------------

def test_format_body_includes_messages():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    body = _format_conversation_body(messages, [], [])
    assert "**User**: Hello" in body
    assert "**Jarvis**: Hi there" in body


def test_format_body_includes_wiki_links():
    body = _format_conversation_body(
        [{"role": "user", "content": "test"}],
        ["projects/jarvis.md", "inbox/idea.md"],
        [],
    )
    assert "[[projects/jarvis.md|" in body
    assert "[[inbox/idea.md|" in body


def test_format_body_includes_topics():
    body = _format_conversation_body(
        [{"role": "user", "content": "test"}],
        [],
        ["python", "architecture"],
    )
    assert "python" in body
    assert "architecture" in body


def test_format_body_truncates_long_messages():
    messages = [{"role": "user", "content": "X" * 3000}]
    body = _format_conversation_body(messages, [], [])
    assert len(body) < 3000  # Should be truncated


# ---------------------------------------------------------------------------
# save_session_to_memory (integration)
# ---------------------------------------------------------------------------

async def test_save_session_to_memory_creates_note(ws):
    sid = create_session()
    add_message(sid, "user", "Tell me about Jarvis")
    add_message(sid, "assistant", "Jarvis is your personal assistant")
    record_tool_use(sid, "write_note")  # active tool triggers save
    record_note_access(sid, "projects/jarvis.md")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    assert note_path is not None
    assert note_path.startswith("conversations/")
    assert note_path.endswith(".md")

    # File exists on disk
    full_path = ws / "memory" / note_path
    assert full_path.exists()


async def test_save_session_to_memory_has_frontmatter(ws):
    sid = create_session()
    add_message(sid, "user", "Plan my week")
    add_message(sid, "assistant", "Here's a plan")
    record_tool_use(sid, "create_plan")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    content = (ws / "memory" / note_path).read_text()
    fm, body = parse_frontmatter(content)

    assert fm["type"] == "conversation"
    assert fm["session_id"] == sid
    assert "conversation" in fm["tags"]
    assert "planning" in fm["tags"]
    assert fm["message_count"] == 2


async def test_save_session_to_memory_has_related(ws):
    sid = create_session()
    add_message(sid, "user", "Read project notes")
    add_message(sid, "assistant", "Done")
    record_tool_use(sid, "open_note")
    record_note_access(sid, "projects/jarvis.md")
    record_note_access(sid, "inbox/idea.md")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    content = (ws / "memory" / note_path).read_text()
    fm, _ = parse_frontmatter(content)

    assert "projects/jarvis.md" in fm["related"]
    assert "inbox/idea.md" in fm["related"]


async def test_save_session_to_memory_has_wiki_links(ws):
    sid = create_session()
    add_message(sid, "user", "Check my notes")
    add_message(sid, "assistant", "Found them")
    record_tool_use(sid, "open_note")
    record_note_access(sid, "daily/today.md")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    content = (ws / "memory" / note_path).read_text()
    assert "[[daily/today.md|" in content


async def test_save_session_to_memory_skips_short(ws):
    sid = create_session()
    add_message(sid, "user", "Hi")  # Only 1 message

    result = await save_session_to_memory(sid, workspace_path=ws)
    assert result is None


async def test_save_session_to_memory_saves_trivial(ws):
    """Even a short exchange like 'hello'/'hi' is saved — all conversations matter."""
    sid = create_session()
    add_message(sid, "user", "hello")
    add_message(sid, "assistant", "Hi there! How can I help?")

    result = await save_session_to_memory(sid, workspace_path=ws)
    assert result is not None


async def test_save_session_to_memory_saves_when_active_tools_used(ws):
    """Even a short session is saved if an active (write) tool was used."""
    sid = create_session()
    add_message(sid, "user", "hello")
    add_message(sid, "assistant", "Hi! I created a note for you.")
    record_tool_use(sid, "write_note")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    assert note_path is not None


async def test_save_session_to_memory_saves_with_passive_tools(ws):
    """Sessions with passive tools are saved — all conversations matter."""
    sid = create_session()
    add_message(sid, "user", "hello")
    add_message(sid, "assistant", "Hi! I searched your notes.")
    record_tool_use(sid, "search_notes")

    result = await save_session_to_memory(sid, workspace_path=ws)
    assert result is not None


async def test_save_session_to_memory_saves_when_long_input(ws):
    """A single exchange with substantial user content (300+ chars) is saved."""
    sid = create_session()
    add_message(sid, "user", "I need to plan my week carefully. I have meetings on Monday morning and Wednesday afternoon, a dentist appointment on Thursday at 2pm, and I want to finish the quarterly report by Friday. Also need to schedule a call with the marketing team about the new campaign and review the budget proposal that was sent last week. Can you help me organize all of this?")
    add_message(sid, "assistant", "Here's a plan for your week.")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    assert note_path is not None


async def test_save_session_to_memory_saves_multi_exchange(ws):
    """Multiple exchanges with meaningful content are saved."""
    sid = create_session()
    add_message(sid, "user", "I want to organize my notes about the project architecture and database design")
    add_message(sid, "assistant", "Sure, let me help you with that.")
    add_message(sid, "user", "The backend uses FastAPI with SQLite for the operational database and markdown files for persistent storage")
    add_message(sid, "assistant", "Got it! That's a solid architecture.")
    add_message(sid, "user", "Can you create a summary of the key components?")
    add_message(sid, "assistant", "Here's the summary of your project architecture...")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    assert note_path is not None


async def test_save_session_to_memory_skips_missing():
    result = await save_session_to_memory("nonexistent")
    assert result is None


async def test_save_session_to_memory_tagged_with_topics(ws):
    sid = create_session()
    # Use an active tool to pass the substance check
    add_message(sid, "user", "architecture design patterns for backend services and distributed systems")
    add_message(sid, "assistant", "Here are some patterns for backend architecture")
    record_tool_use(sid, "write_note")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    content = (ws / "memory" / note_path).read_text()
    fm, _ = parse_frontmatter(content)

    # Should have topic-based tags beyond just "conversation"
    assert len(fm["tags"]) > 1


async def test_save_session_to_memory_deduplicates(ws):
    """Calling save_session_to_memory twice should not create two files."""
    sid = create_session()
    add_message(sid, "user", "Create a note about testing")
    add_message(sid, "assistant", "Done, note created.")
    record_tool_use(sid, "write_note")

    path1 = await save_session_to_memory(sid, workspace_path=ws)
    assert path1 is not None

    # Second save (simulating tab switch / reconnect)
    path2 = await save_session_to_memory(sid, workspace_path=ws)
    assert path2 is not None

    # Should reuse the same file, not create a new one
    assert path1 == path2

    # Only one file should exist in conversations/
    convos = list((ws / "memory" / "conversations").glob("*.md"))
    assert len(convos) == 1


async def test_save_session_to_memory_saves_meaningful_question(ws):
    """A single meaningful question (>= 50 chars) should be saved to memory."""
    sid = create_session()
    add_message(sid, "user", "Opowiedz mi o stoicyzmie i jak mogę go stosować w codziennym życiu")
    add_message(sid, "assistant", "Stoicyzm to filozofia...")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    assert note_path is not None


async def test_save_session_to_memory_saves_two_exchanges(ws):
    """Two full exchanges (4 messages) should always be saved."""
    sid = create_session()
    add_message(sid, "user", "Kim jesteś?")
    add_message(sid, "assistant", "Jestem Jarvis.")
    add_message(sid, "user", "Co potrafisz?")
    add_message(sid, "assistant", "Mogę pomóc z wieloma rzeczami.")

    note_path = await save_session_to_memory(sid, workspace_path=ws)
    assert note_path is not None
