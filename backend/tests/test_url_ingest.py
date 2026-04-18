from pathlib import Path

import pytest

from services.ingest import IngestError
from services import url_ingest


def test_detect_url_type_youtube_variants():
    t1, vid1 = url_ingest.detect_url_type("https://youtube.com/watch?v=dQw4w9WgXcQ")
    t2, vid2 = url_ingest.detect_url_type("https://youtu.be/dQw4w9WgXcQ")
    t3, vid3 = url_ingest.detect_url_type("https://youtube.com/shorts/dQw4w9WgXcQ")
    t4, vid4 = url_ingest.detect_url_type("https://youtube.com/embed/dQw4w9WgXcQ")

    assert t1 == "youtube" and vid1 == "dQw4w9WgXcQ"
    assert t2 == "youtube" and vid2 == "dQw4w9WgXcQ"
    assert t3 == "youtube" and vid3 == "dQw4w9WgXcQ"
    assert t4 == "youtube" and vid4 == "dQw4w9WgXcQ"


def test_detect_url_type_webpage_and_invalid():
    t1, vid1 = url_ingest.detect_url_type("https://example.com/article")
    t2, vid2 = url_ingest.detect_url_type("file:///tmp/x")

    assert t1 == "webpage"
    assert vid1 is None
    assert t2 == "invalid"
    assert vid2 is None


@pytest.mark.anyio
async def test_ingest_url_rejects_invalid_scheme():
    with pytest.raises(IngestError):
        await url_ingest.ingest_url("javascript:alert(1)")


@pytest.mark.anyio
async def test_ingest_url_youtube_path(monkeypatch):
    async def fake_ingest_youtube(video_id: str, url: str, folder: str, workspace_path=None):
        return {
            "path": f"{folder}/yt-{video_id}.md",
            "title": "YouTube: dQw4w9WgXcQ",
            "type": "youtube",
            "source": url,
            "word_count": 123,
        }

    monkeypatch.setattr(url_ingest, "_ingest_youtube", fake_ingest_youtube)
    monkeypatch.setattr("services.privacy.url_ingest_enabled", lambda *a, **kw: True)

    result = await url_ingest.ingest_url("https://youtu.be/dQw4w9WgXcQ", folder="knowledge")

    assert result["type"] == "youtube"
    assert result["path"].startswith("knowledge/")


@pytest.mark.anyio
async def test_ingest_url_webpage_path(monkeypatch):
    async def fake_ingest_web(url: str, folder: str, workspace_path=None):
        return {
            "path": f"{folder}/article.md",
            "title": "Example",
            "type": "article",
            "source": url,
            "word_count": 456,
        }

    monkeypatch.setattr(url_ingest, "_ingest_webpage", fake_ingest_web)
    monkeypatch.setattr("services.privacy.url_ingest_enabled", lambda *a, **kw: True)

    result = await url_ingest.ingest_url("https://example.com/post", folder="inbox")

    assert result["type"] == "article"
    assert result["path"] == "inbox/article.md"


@pytest.mark.anyio
async def test_ingest_url_with_summary(monkeypatch):
    async def fake_ingest_web(url: str, folder: str, workspace_path=None):
        return {
            "path": f"{folder}/article.md",
            "title": "Example",
            "type": "article",
            "source": url,
            "word_count": 111,
        }

    async def fake_smart_enrich(note_path: str, api_key: str, workspace_path=None):
        return {"summary": "Short summary"}

    monkeypatch.setattr(url_ingest, "_ingest_webpage", fake_ingest_web)
    monkeypatch.setattr("services.privacy.url_ingest_enabled", lambda *a, **kw: True)

    import services.ingest as ingest_mod
    monkeypatch.setattr(ingest_mod, "smart_enrich", fake_smart_enrich)

    result = await url_ingest.ingest_url(
        "https://example.com/post",
        summarize=True,
        api_key="test-key",
    )

    assert result["summary"] == "Short summary"
