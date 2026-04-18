import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# Disable embedding model loading during tests to avoid loading a 200MB
# model into every test run. Individual tests that need embeddings can
# clear this env var in their own fixture.
os.environ.setdefault("JARVIS_DISABLE_EMBEDDINGS", "1")

from main import app


def _spacy_models_available() -> bool:
    """Check if at least the Polish spaCy model is loadable.

    CI sometimes can't download spaCy model wheels from GitHub releases
    (transient 5xx). When that happens we skip NER-dependent tests rather
    than fail the whole suite — entity_extraction degrades to regex.
    """
    try:
        import spacy
        spacy.load("pl_core_news_sm")
        return True
    except Exception:
        return False


_SPACY_AVAILABLE = _spacy_models_available()


def pytest_collection_modifyitems(config, items):
    """Skip entity-extraction tests when spaCy NER models are unavailable."""
    if _SPACY_AVAILABLE:
        return
    skip_ner = pytest.mark.skip(reason="spaCy NER models unavailable (CI download may have failed)")
    for item in items:
        if "entity_extraction" in item.nodeid or "test_entity_enrichment" in item.nodeid:
            item.add_marker(skip_ner)


@pytest.fixture(autouse=True)
def _no_auto_persist():
    """Prevent add_message from auto-persisting sessions to the real workspace during tests."""
    with patch("services.session_service._auto_persist"):
        yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
