import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

# Disable embedding model loading during tests to avoid loading a 200MB
# model into every test run. Individual tests that need embeddings can
# clear this env var in their own fixture.
os.environ.setdefault("JARVIS_DISABLE_EMBEDDINGS", "1")

from main import app

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
