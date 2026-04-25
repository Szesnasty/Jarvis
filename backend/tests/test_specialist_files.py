import json
from pathlib import Path

import pytest

from services.specialist_service import (
    SpecialistNotFoundError,
    copy_file_to_specialist,
    count_specialist_files,
    create_specialist,
    delete_specialist,
    delete_specialist_file,
    list_specialist_files,
    reset_state,
    save_specialist_file,
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


SAMPLE_DATA = {"name": "Health Guide", "role": "Health assistant", "icon": "\U0001f3e5"}


# --- save_specialist_file ---


def test_save_file(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = save_specialist_file("health-guide", "notes.md", b"# Notes\nHello", workspace_path=ws)
    assert result["filename"] == "notes.md"
    assert result["size"] == len(b"# Notes\nHello")
    assert (ws / "agents" / "health-guide" / "notes.md").exists()


def test_save_file_duplicate_name(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    save_specialist_file("health-guide", "notes.md", b"first", workspace_path=ws)
    result = save_specialist_file("health-guide", "notes.md", b"second", workspace_path=ws)
    assert result["filename"] == "notes-1.md"
    assert (ws / "agents" / "health-guide" / "notes-1.md").exists()


def test_save_file_nonexistent_specialist(ws):
    with pytest.raises(SpecialistNotFoundError):
        save_specialist_file("nonexistent", "notes.md", b"data", workspace_path=ws)


def test_save_file_path_traversal_is_sanitized(ws):
    """Path traversal attempts are stripped down to the safe leaf name."""
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = save_specialist_file("health-guide", "../evil.md", b"data", workspace_path=ws)
    # Saved as plain 'evil.md' inside the specialist dir — no traversal possible.
    assert result["filename"] == "evil.md"


def test_save_file_disallowed_extension(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    with pytest.raises(ValueError, match="Unsupported file type"):
        save_specialist_file("health-guide", "script.exe", b"data", workspace_path=ws)


def test_save_file_polish_characters_sanitized(ws):
    """Filenames with Polish characters no longer 422 — they get sanitized."""
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = save_specialist_file(
        "health-guide", "Notatka — szwagier.pdf", b"data", workspace_path=ws
    )
    # Polish chars and em-dash replaced with '-'; extension preserved.
    assert result["filename"].endswith(".pdf")
    assert "/" not in result["filename"]
    assert ".." not in result["filename"]


def test_save_file_parens_and_commas_sanitized(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = save_specialist_file(
        "health-guide", "report (final), v2.pdf", b"data", workspace_path=ws
    )
    assert result["filename"].endswith(".pdf")
    assert "(" not in result["filename"]
    assert "," not in result["filename"]


def test_save_file_leading_underscore_sanitized(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = save_specialist_file(
        "health-guide", "_internal.txt", b"data", workspace_path=ws
    )
    # Stem must start with alphanumeric per validator → fallback prefix added.
    assert result["filename"].endswith(".txt")
    import re as _re
    assert _re.match(r"^[a-zA-Z0-9]", result["filename"])


def test_save_file_only_special_chars_falls_back(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = save_specialist_file("health-guide", "!!!.md", b"data", workspace_path=ws)
    assert result["filename"] == "file.md"


def test_save_file_empty_filename_rejected(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    with pytest.raises(ValueError, match="Filename is required"):
        save_specialist_file("health-guide", "", b"data", workspace_path=ws)


# --- list_specialist_files ---


def test_list_files_empty(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    result = list_specialist_files("health-guide", workspace_path=ws)
    assert result == []


def test_list_files_returns_uploaded(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    save_specialist_file("health-guide", "a.md", b"aaa", workspace_path=ws)
    save_specialist_file("health-guide", "b.txt", b"bbb", workspace_path=ws)
    result = list_specialist_files("health-guide", workspace_path=ws)
    filenames = [f["filename"] for f in result]
    assert "a.md" in filenames
    assert "b.txt" in filenames
    assert len(result) == 2


def test_list_files_ignores_non_allowed_extensions(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    files_dir = ws / "agents" / "health-guide"
    files_dir.mkdir(parents=True, exist_ok=True)
    (files_dir / "readme.md").write_text("ok")
    (files_dir / "image.png").write_bytes(b"\x89PNG")  # not in allowed list
    result = list_specialist_files("health-guide", workspace_path=ws)
    assert len(result) == 1
    assert result[0]["filename"] == "readme.md"


def test_list_files_nonexistent_specialist(ws):
    with pytest.raises(SpecialistNotFoundError):
        list_specialist_files("nonexistent", workspace_path=ws)


# --- delete_specialist_file ---


def test_delete_file(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    save_specialist_file("health-guide", "notes.md", b"data", workspace_path=ws)
    delete_specialist_file("health-guide", "notes.md", workspace_path=ws)
    assert not (ws / "agents" / "health-guide" / "notes.md").exists()


def test_delete_file_not_found(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    with pytest.raises(FileNotFoundError):
        delete_specialist_file("health-guide", "missing.md", workspace_path=ws)


def test_delete_file_path_traversal(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    with pytest.raises(ValueError, match="Invalid filename"):
        delete_specialist_file("health-guide", "../../etc/passwd", workspace_path=ws)


# --- count_specialist_files ---


def test_count_files_zero(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    assert count_specialist_files("health-guide", workspace_path=ws) == 0


def test_count_files_after_upload(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    save_specialist_file("health-guide", "a.md", b"a", workspace_path=ws)
    save_specialist_file("health-guide", "b.txt", b"b", workspace_path=ws)
    assert count_specialist_files("health-guide", workspace_path=ws) == 2


# --- copy_file_to_specialist ---


def test_copy_file(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    source = ws / "temp-article.md"
    source.write_text("# Article\nContent here")
    result = copy_file_to_specialist("health-guide", source, title="My Article", workspace_path=ws)
    assert result["filename"] == "temp-article.md"
    assert result["title"] == "My Article"
    assert (ws / "agents" / "health-guide" / "temp-article.md").exists()


def test_copy_file_duplicate(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    source = ws / "article.md"
    source.write_text("content")
    copy_file_to_specialist("health-guide", source, workspace_path=ws)
    result = copy_file_to_specialist("health-guide", source, workspace_path=ws)
    assert result["filename"] == "article-1.md"


# --- delete_specialist cleans up files dir ---


def test_delete_specialist_removes_files_dir(ws):
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    save_specialist_file("health-guide", "notes.md", b"data", workspace_path=ws)
    files_dir = ws / "agents" / "health-guide"
    assert files_dir.is_dir()
    delete_specialist("health-guide", workspace_path=ws)
    assert not files_dir.exists()


def test_delete_specialist_without_files_dir(ws):
    """Deleting a specialist that never had files should not error."""
    create_specialist(SAMPLE_DATA, workspace_path=ws)
    delete_specialist("health-guide", workspace_path=ws)
    assert not (ws / "agents" / "health-guide").exists()


# --- list_specialists includes file_count ---


def test_list_specialists_includes_file_count(ws):
    from services.specialist_service import list_specialists

    create_specialist(SAMPLE_DATA, workspace_path=ws)
    save_specialist_file("health-guide", "a.md", b"a", workspace_path=ws)
    save_specialist_file("health-guide", "b.txt", b"b", workspace_path=ws)
    result = list_specialists(workspace_path=ws)
    assert result[0]["file_count"] == 2
