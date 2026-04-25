"""Tests for executor section-type passthrough for client-estimator (step 28e)."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.tools.executor import execute_tool


@pytest.mark.anyio
async def test_client_estimator_routes_to_pipeline(tmp_path):
    """When specialist_id='client-estimator', search_notes uses pipeline.retrieve."""
    fake_results = [
        {"path": "knowledge/doc/02-risks.md", "title": "Risks", "section_type": "risks"},
    ]

    with patch(
        "services.retrieval.pipeline.retrieve",
        new=AsyncMock(return_value=fake_results),
    ) as mock_retrieve:
        result = await execute_tool(
            "search_notes",
            {"query": "what risks does the document mention?", "limit": 5},
            workspace_path=tmp_path,
            specialist_id="client-estimator",
        )

    mock_retrieve.assert_called_once()
    call_kwargs = mock_retrieve.call_args
    assert call_kwargs[0][0] == "what risks does the document mention?"
    data = json.loads(result)
    assert data[0]["section_type"] == "risks"


@pytest.mark.anyio
async def test_other_specialist_uses_memory_service(tmp_path):
    """When specialist_id is not client-estimator, search_notes uses memory_service."""
    fake_results = [
        {"path": "inbox/note.md", "title": "Note"},
    ]

    with patch(
        "services.memory_service.list_notes",
        new=AsyncMock(return_value=fake_results),
    ) as mock_list, patch(
        "services.retrieval.pipeline.retrieve",
        new=AsyncMock(return_value=[]),
    ) as mock_pipeline:
        result = await execute_tool(
            "search_notes",
            {"query": "some query"},
            workspace_path=tmp_path,
            specialist_id="jira-strategist",
        )

    mock_list.assert_called_once()
    mock_pipeline.assert_not_called()


@pytest.mark.anyio
async def test_no_specialist_uses_memory_service(tmp_path):
    """With specialist_id=None, search_notes uses memory_service (default path)."""
    fake_results: list = []

    with patch(
        "services.memory_service.list_notes",
        new=AsyncMock(return_value=fake_results),
    ) as mock_list, patch(
        "services.retrieval.pipeline.retrieve",
        new=AsyncMock(return_value=[]),
    ) as mock_pipeline:
        await execute_tool(
            "search_notes",
            {"query": "anything"},
            workspace_path=tmp_path,
            specialist_id=None,
        )

    mock_list.assert_called_once()
    mock_pipeline.assert_not_called()
