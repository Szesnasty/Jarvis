import json

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from services.preference_service import (
    delete_preference,
    format_for_prompt,
    load_preferences,
    save_preference,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "app").mkdir()
    return tmp_path


def test_save_preference(ws):
    save_preference("style", "Be concise", ws)
    path = ws / "app" / "preferences.json"
    assert path.exists()


def test_save_preference_key_value(ws):
    save_preference("style", "Be concise", ws)
    prefs = json.loads((ws / "app" / "preferences.json").read_text())
    assert prefs["style"] == "Be concise"


def test_load_preferences_empty(ws):
    assert load_preferences(ws) == {}


def test_load_preferences_returns_all(ws):
    save_preference("style", "Concise", ws)
    save_preference("behavior", "Ask first", ws)
    prefs = load_preferences(ws)
    assert prefs["style"] == "Concise"
    assert prefs["behavior"] == "Ask first"


def test_overwrite_preference(ws):
    save_preference("style", "Verbose", ws)
    save_preference("style", "Concise", ws)
    prefs = load_preferences(ws)
    assert prefs["style"] == "Concise"


def test_delete_preference(ws):
    save_preference("style", "Concise", ws)
    save_preference("behavior", "Ask first", ws)
    delete_preference("style", ws)
    prefs = load_preferences(ws)
    assert "style" not in prefs
    assert "behavior" in prefs


def test_preferences_in_system_prompt(ws):
    save_preference("style", "Be concise", ws)
    text = format_for_prompt(ws)
    assert text is not None
    assert "[style]" in text
    assert "Be concise" in text


def test_preferences_survive_restart(ws):
    save_preference("style", "Concise", ws)
    # Simulate restart by loading from a fresh call
    prefs = load_preferences(ws)
    assert prefs["style"] == "Concise"


@pytest.mark.anyio
async def test_preference_via_tool(ws):
    from services.tools import execute_tool

    result = await execute_tool(
        "save_preference",
        {"rule": "Be brief", "category": "style"},
        workspace_path=ws,
    )
    assert "Preference saved" in result
    prefs = load_preferences(ws)
    assert prefs["style"] == "Be brief"


def test_invalid_preference_key_rejected(ws):
    with pytest.raises(ValueError):
        save_preference("", "value", ws)
    with pytest.raises(ValueError):
        save_preference("   ", "value", ws)
