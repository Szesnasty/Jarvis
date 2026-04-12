import json

import pytest

from services.specialist_service import (
    SpecialistNotFoundError,
    activate_specialist,
    build_specialist_prompt,
    create_specialist,
    deactivate_specialist,
    filter_tools,
    get_active_specialist,
    get_specialist,
    list_specialists,
    reset_state,
    suggest_specialist,
)

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "agents").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


SAMPLE_DATA = {
    "name": "Health Guide",
    "role": "You are a health-focused assistant.",
    "sources": ["memory/knowledge/health/", "memory/daily/"],
    "style": {"tone": "calm", "format": "checklist", "length": "concise"},
    "rules": ["Never diagnose conditions", "Reference user notes first"],
    "tools": ["search_notes", "read_note"],
    "examples": [
        {"user": "How has my sleep been?", "assistant": "Based on your notes..."}
    ],
    "icon": "🏥",
}


SAMPLE_TOOLS = [
    {"name": "search_notes", "description": "Search notes"},
    {"name": "read_note", "description": "Read a note"},
    {"name": "write_note", "description": "Write a note"},
    {"name": "append_note", "description": "Append to a note"},
    {"name": "query_graph", "description": "Query the graph"},
]


def test_create_specialist_saves_json(ws):
    spec = create_specialist(SAMPLE_DATA, workspace_path=ws)
    filepath = ws / "agents" / f"{spec['id']}.json"
    assert filepath.exists()
    data = json.loads(filepath.read_text())
    assert data["name"] == "Health Guide"


def test_create_specialist_schema(ws):
    spec = create_specialist(SAMPLE_DATA, workspace_path=ws)
    assert spec["name"] == "Health Guide"
    assert spec["role"] == "You are a health-focused assistant."
    assert len(spec["sources"]) == 2
    assert len(spec["tools"]) == 2
    assert len(spec["rules"]) == 2
    assert spec["icon"] == "🏥"
    assert "created_at" in spec
    assert "updated_at" in spec


def test_create_specialist_validates_name(ws):
    with pytest.raises(ValueError, match="name"):
        create_specialist({"name": ""}, workspace_path=ws)


def test_list_specialists(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    create_specialist({"name": "Writer"}, workspace_path=ws)
    result = list_specialists(workspace_path=ws)
    assert len(result) == 2
    names = [s["name"] for s in result]
    assert "Health Guide" in names
    assert "Writer" in names


def test_list_specialists_empty(ws):
    result = list_specialists(workspace_path=ws)
    assert result == []


def test_get_specialist(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    spec = get_specialist("health-guide", workspace_path=ws)
    assert spec["name"] == "Health Guide"
    assert spec["role"] == "You are a health-focused assistant."


def test_get_specialist_not_found(ws):
    with pytest.raises(SpecialistNotFoundError):
        get_specialist("nonexistent", workspace_path=ws)


def test_activate_specialist_modifies_prompt(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    activate_specialist("health-guide", workspace_path=ws)
    active = get_active_specialist()
    assert active is not None
    prompt = build_specialist_prompt(active, "Base prompt.")
    assert "Health Guide" in prompt
    assert "health-focused" in prompt
    assert "Never diagnose" in prompt


def test_activate_specialist_sets_active(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    activate_specialist("health-guide", workspace_path=ws)
    active = get_active_specialist()
    assert active is not None
    assert active["id"] == "health-guide"


def test_deactivate_returns_to_base(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    activate_specialist("health-guide", workspace_path=ws)
    assert get_active_specialist() is not None
    deactivate_specialist()
    assert get_active_specialist() is None


def test_scoped_search(ws):
    """filter_tools + source scoping tested via _scope_results in context_builder."""
    from services.context_builder import _scope_results

    results = [
        {"path": "knowledge/health/symptoms.md"},
        {"path": "daily/2026-01-01.md"},
        {"path": "projects/jarvis.md"},
    ]
    sources = ["memory/knowledge/health/", "memory/daily/"]
    scoped = _scope_results(results, sources)
    assert len(scoped) == 2
    paths = [r["path"] for r in scoped]
    assert "knowledge/health/symptoms.md" in paths
    assert "daily/2026-01-01.md" in paths


def test_scoped_search_no_leakage(ws):
    from services.context_builder import _scope_results

    results = [
        {"path": "projects/secret.md"},
        {"path": "inbox/random.md"},
    ]
    sources = ["memory/knowledge/health/"]
    scoped = _scope_results(results, sources)
    assert len(scoped) == 0


def test_tool_filter_whitelist(ws):
    specialist = {"tools": ["search_notes", "read_note"]}
    filtered = filter_tools(SAMPLE_TOOLS, specialist)
    names = [t["name"] for t in filtered]
    assert "search_notes" in names
    assert "read_note" in names
    assert len(filtered) == 2


def test_tool_filter_blocks_restricted(ws):
    specialist = {"tools": ["search_notes"]}
    filtered = filter_tools(SAMPLE_TOOLS, specialist)
    names = [t["name"] for t in filtered]
    assert "write_note" not in names
    assert "append_note" not in names
    assert "query_graph" not in names


def test_tool_filter_empty_allows_all():
    specialist = {"tools": []}
    filtered = filter_tools(SAMPLE_TOOLS, specialist)
    assert len(filtered) == len(SAMPLE_TOOLS)


def test_tool_filter_no_specialist():
    filtered = filter_tools(SAMPLE_TOOLS, None)
    assert len(filtered) == len(SAMPLE_TOOLS)


def test_suggest_specialist(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    suggestion = suggest_specialist("How has my health been?", workspace_path=ws)
    assert suggestion is not None
    assert suggestion["name"] == "Health Guide"


def test_suggest_specialist_no_match(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    suggestion = suggest_specialist("zxywq gibberish 12345", workspace_path=ws)
    assert suggestion is None
