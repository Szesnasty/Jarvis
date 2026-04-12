import json

import pytest

from services.specialist_service import (
    SpecialistNotFoundError,
    activate_specialist,
    create_specialist,
    deactivate_specialist,
    delete_specialist,
    get_active_specialist,
    get_specialist,
    list_specialists,
    reset_state,
    update_specialist,
)

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / ".trash").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _reset():
    reset_state()
    yield
    reset_state()


SAMPLE_DATA = {
    "name": "Health Guide",
    "role": "Health assistant",
    "icon": "🏥",
}


def test_edit_specialist_updates_file(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    update_specialist("health-guide", {"role": "Updated role"}, workspace_path=ws)
    filepath = ws / "agents" / "health-guide.json"
    data = json.loads(filepath.read_text())
    assert data["role"] == "Updated role"


def test_edit_specialist_preserves_id(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    updated = update_specialist("health-guide", {"name": "New Name"}, workspace_path=ws)
    assert updated["id"] == "health-guide"
    assert updated["name"] == "New Name"


def test_delete_specialist_moves_to_trash(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    delete_specialist("health-guide", workspace_path=ws)
    assert not (ws / "agents" / "health-guide.json").exists()
    assert (ws / ".trash" / "health-guide.json").exists()


def test_delete_specialist_removes_from_list(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    delete_specialist("health-guide", workspace_path=ws)
    result = list_specialists(workspace_path=ws)
    assert len(result) == 0


def test_delete_active_specialist_deactivates(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    activate_specialist("health-guide", workspace_path=ws)
    assert get_active_specialist() is not None
    delete_specialist("health-guide", workspace_path=ws)
    assert get_active_specialist() is None


def test_activate_nonexistent_raises(ws):
    with pytest.raises(SpecialistNotFoundError):
        activate_specialist("nonexistent", workspace_path=ws)


def test_activate_while_another_active(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    create_specialist({"name": "Writer"}, workspace_path=ws)
    activate_specialist("health-guide", workspace_path=ws)
    activate_specialist("writer", workspace_path=ws)
    active = get_active_specialist()
    assert active["id"] == "writer"


def test_specialist_survives_restart(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    reset_state()
    spec = get_specialist("health-guide", workspace_path=ws)
    assert spec["name"] == "Health Guide"
