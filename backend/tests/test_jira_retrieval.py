"""Tests for step 22f — Jira-aware hybrid retrieval.

Covers:
- Intent parser (key extraction, sprint detection, risk hints)
- Enrichment signal gating
- Post-fusion boost capping
- Structured context sections
- Backward compatibility with non-Jira workspaces
- Facet pre-filtering
"""

import json
import os
import textwrap
from dataclasses import dataclass
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.memory_service import create_note
from services.retrieval.intent import FacetFilter, QueryIntent
from services.retrieval.intent_parser import parse_intent
from services.retrieval.pipeline import (
    BOOST_CAP,
    BOOST_EXPLICIT_KEY,
    BOOST_SPRINT_ACTIVE,
    _compute_enrichment_score,
    _compute_post_fusion_boost,
    _extract_issue_key_from_path,
    _matches_facets,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ── Intent parser tests ────────────────────────────────────────────


class TestIntentParserKey:
    """test_intent_parser_key: issue keys extracted, wants_issues_only set."""

    def test_single_key(self):
        intent = parse_intent("what blocks ONB-142?")
        assert intent.keys_in_query == ["ONB-142"]
        assert intent.wants_issues_only is True

    def test_multiple_keys(self):
        intent = parse_intent("compare ONB-142 with AUTH-88")
        assert "ONB-142" in intent.keys_in_query
        assert "AUTH-88" in intent.keys_in_query
        assert intent.wants_issues_only is True

    def test_no_keys(self):
        intent = parse_intent("how to improve sleep?")
        assert intent.keys_in_query == []
        assert intent.wants_issues_only is False

    def test_project_key_extracted(self):
        intent = parse_intent("show me ONB-142")
        assert intent.facets.project_key == ["ONB"]


class TestIntentParserSprint:
    """test_intent_parser_sprint: sprint filter + risk hint."""

    def test_current_sprint(self):
        intent = parse_intent("what's risky this sprint?")
        assert intent.sprint_filter == "active"
        assert intent.facets.sprint_state == ["active"]
        assert intent.risk_hint == "high-risk"
        assert intent.wants_issues_only is True

    def test_this_sprint_polish(self):
        intent = parse_intent("pokaż aktualny sprint")
        assert intent.sprint_filter == "active"

    def test_no_sprint(self):
        intent = parse_intent("show me project progress")
        assert intent.sprint_filter is None


class TestIntentParserStatus:
    """Status word detection."""

    def test_open_status(self):
        intent = parse_intent("what's open?")
        assert intent.wants_open_only is True
        assert "To Do" in intent.facets.status_category or "In Progress" in intent.facets.status_category

    def test_done_status(self):
        intent = parse_intent("which tasks are done?")
        assert "Done" in intent.facets.status_category


class TestIntentParserBusinessArea:
    """Business area hint detection."""

    def test_onboarding_area(self):
        intent = parse_intent("onboarding issues this sprint")
        assert intent.business_area_hint == "onboarding"

    def test_billing_area(self):
        intent = parse_intent("billing bugs")
        assert intent.business_area_hint == "billing"


class TestIntentParserRisk:
    """Risk/ambiguity hint detection."""

    def test_blocker_risk(self):
        intent = parse_intent("show blockers")
        assert intent.risk_hint == "high-risk"

    def test_unclear_ambiguity(self):
        intent = parse_intent("which tasks are unclear?")
        assert intent.risk_hint == "unclear"


class TestIntentParserAssignee:
    """Assignee extraction."""

    def test_assigned_to(self):
        intent = parse_intent("tasks assigned to john")
        assert intent.assignee_filter == "john"


# ── Enrichment signal tests ───────────────────────────────────────


class TestEnrichmentSignalGated:
    """test_enrichment_signal_gated: non-issue candidates get zero."""

    def test_no_enrichment(self):
        intent = QueryIntent(text="test", business_area_hint="onboarding")
        score = _compute_enrichment_score(None, intent)
        assert score == 0.0

    def test_business_area_match(self):
        intent = QueryIntent(text="test", business_area_hint="onboarding")
        enrichment = {"business_area": "onboarding", "risk_level": "low", "ambiguity_level": "clear"}
        score = _compute_enrichment_score(enrichment, intent)
        assert score == 0.5

    def test_risk_match(self):
        intent = QueryIntent(text="test", risk_hint="high-risk")
        enrichment = {"business_area": "infra", "risk_level": "high", "ambiguity_level": "clear"}
        score = _compute_enrichment_score(enrichment, intent)
        assert score == 0.3

    def test_ambiguity_match(self):
        intent = QueryIntent(text="test", risk_hint="unclear")
        enrichment = {"business_area": "infra", "risk_level": "low", "ambiguity_level": "unclear"}
        score = _compute_enrichment_score(enrichment, intent)
        assert score == 0.2

    def test_combined_match(self):
        intent = QueryIntent(text="test", business_area_hint="onboarding", risk_hint="high-risk")
        enrichment = {"business_area": "onboarding", "risk_level": "high", "ambiguity_level": "clear"}
        score = _compute_enrichment_score(enrichment, intent)
        assert score == 0.8

    def test_capped_at_1(self):
        intent = QueryIntent(text="test", business_area_hint="billing", risk_hint="unclear")
        enrichment = {"business_area": "billing", "risk_level": "high", "ambiguity_level": "unclear"}
        score = _compute_enrichment_score(enrichment, intent)
        assert score <= 1.0


# ── Post-fusion boost tests ───────────────────────────────────────


class TestBoostCap:
    """test_boost_cap: stacking boosts never exceeds BOOST_CAP."""

    def test_explicit_key_boost(self):
        intent = QueryIntent(text="ONB-142", keys_in_query=["ONB-142"])
        boost = _compute_post_fusion_boost("jira/ONB/ONB-142.md", intent, None)
        assert boost == BOOST_EXPLICIT_KEY

    def test_sprint_boost(self):
        intent = QueryIntent(text="sprint", sprint_filter="active")
        boost = _compute_post_fusion_boost("jira/PROJ/PROJ-1.md", intent, None)
        assert boost == BOOST_SPRINT_ACTIVE

    def test_stacked_boost_capped(self):
        intent = QueryIntent(
            text="ONB-142 sprint",
            keys_in_query=["ONB-142"],
            sprint_filter="active",
        )
        boost = _compute_post_fusion_boost("jira/ONB/ONB-142.md", intent, None)
        assert boost == min(BOOST_EXPLICIT_KEY + BOOST_SPRINT_ACTIVE, BOOST_CAP)
        assert boost <= BOOST_CAP

    def test_no_boost_for_notes(self):
        intent = QueryIntent(text="ONB-142", keys_in_query=["ONB-142"])
        boost = _compute_post_fusion_boost("projects/readme.md", intent, None)
        assert boost == 0.0


# ── Facet filter tests ────────────────────────────────────────────


class TestFacetFilter:
    """test_filter_reduces_candidates: facet filtering."""

    def test_status_filter(self):
        fm = {"status_category": "To Do", "project_key": "ONB"}
        facets = FacetFilter(status_category=["To Do"])
        assert _matches_facets(fm, facets) is True

    def test_status_filter_mismatch(self):
        fm = {"status_category": "Done", "project_key": "ONB"}
        facets = FacetFilter(status_category=["To Do"])
        assert _matches_facets(fm, facets) is False

    def test_project_filter(self):
        fm = {"status_category": "To Do", "project_key": "ONB"}
        facets = FacetFilter(project_key=["ONB"])
        assert _matches_facets(fm, facets) is True

    def test_project_filter_mismatch(self):
        fm = {"status_category": "To Do", "project_key": "AUTH"}
        facets = FacetFilter(project_key=["ONB"])
        assert _matches_facets(fm, facets) is False

    def test_sprint_filter(self):
        fm = {"sprint": "Sprint 14", "sprints": ["Sprint 14"]}
        facets = FacetFilter(sprint_state=["active"])
        assert _matches_facets(fm, facets) is True

    def test_sprint_filter_empty(self):
        fm = {"sprint": "", "sprints": []}
        facets = FacetFilter(sprint_state=["active"])
        assert _matches_facets(fm, facets) is False

    def test_assignee_filter(self):
        fm = {"assignee": "john"}
        facets = FacetFilter(assignee=["john"])
        assert _matches_facets(fm, facets) is True

    def test_empty_facets_pass_all(self):
        fm = {"status_category": "Done"}
        facets = FacetFilter()
        assert facets.is_empty is True


# ── Issue key extraction from path ─────────────────────────────────


class TestIssueKeyFromPath:

    def test_valid_path(self):
        assert _extract_issue_key_from_path("jira/ONB/ONB-142.md") == "ONB-142"

    def test_nested_path(self):
        assert _extract_issue_key_from_path("jira/AUTH/AUTH-88.md") == "AUTH-88"

    def test_non_jira_path(self):
        assert _extract_issue_key_from_path("projects/readme.md") is None


# ── Backward compatibility ─────────────────────────────────────────


class TestBackcompatNoIssues:
    """test_backcompat_no_issues: without Jira data, same results as before."""

    async def test_retrieve_returns_list(self, tmp_path):
        """Verify retrieve() still returns a list (not a tuple)."""
        from services.retrieval import retrieve

        db_path = tmp_path / "jarvis.db"
        await init_database(db_path)

        await create_note(
            "projects/test.md",
            "# Test\nSome content about testing",
            workspace_path=tmp_path,
        )

        results = await retrieve("testing", workspace_path=tmp_path)
        assert isinstance(results, list)

    async def test_no_enrichment_signal_without_flag(self, tmp_path):
        """Without JARVIS_FEATURE_JIRA_RETRIEVAL, no enrichment signal in results."""
        from services.retrieval import retrieve

        db_path = tmp_path / "jarvis.db"
        await init_database(db_path)

        await create_note(
            "projects/test.md",
            "# Test\nContent",
            workspace_path=tmp_path,
        )

        env = {**os.environ}
        env.pop("JARVIS_FEATURE_JIRA_RETRIEVAL", None)
        with patch.dict(os.environ, env, clear=True):
            results = await retrieve("test", workspace_path=tmp_path)

        for r in results:
            signals = r.get("_signals", {})
            assert "enrichment" not in signals


# ── Context sections test ──────────────────────────────────────────


class TestContextSections:
    """test_context_sections: issues, decisions, notes in separate XML sections."""

    async def test_structured_context_with_jira(self, tmp_path):
        """When Jira retrieval is enabled, context has structured sections."""
        from services.context_builder import _build_structured_context

        results = [
            {"path": "jira/ONB/ONB-1.md", "title": "ONB-1 — Bug", "_best_chunk": "some bug description"},
            {"path": "decisions/adr-001.md", "title": "ADR 001", "_best_chunk": "we decided to use X"},
            {"path": "projects/readme.md", "title": "README", "_best_chunk": "project overview"},
        ]

        # Mock DB calls
        with patch("services.context_builder.memory_service") as mock_mem:
            mock_mem._db_path.return_value = tmp_path / "nonexistent.db"
            context = await _build_structured_context(results, tmp_path)

        assert context is not None
        assert "<issues>" in context
        assert "<decisions>" in context
        assert "<notes>" in context
        assert "<issue " in context
        assert "ONB-1" in context

    async def test_no_issues_rolls_over_budget(self, tmp_path):
        """Without issues, all budget goes to notes."""
        from services.context_builder import _build_structured_context

        results = [
            {"path": "projects/readme.md", "title": "README", "_best_chunk": "project overview"},
        ]

        with patch("services.context_builder.memory_service") as mock_mem:
            mock_mem._db_path.return_value = tmp_path / "nonexistent.db"
            context = await _build_structured_context(results, tmp_path)

        assert context is not None
        assert "<issues>" not in context
        assert "<notes>" in context


# ── Integration: retrieve_with_intent ──────────────────────────────


class TestRetrieveWithIntent:
    """Integration test for retrieve_with_intent."""

    async def test_returns_intent_and_results(self, tmp_path):
        from services.retrieval import retrieve_with_intent

        db_path = tmp_path / "jarvis.db"
        await init_database(db_path)

        await create_note(
            "projects/test.md",
            "# Test\nSome content",
            workspace_path=tmp_path,
        )

        intent, results = await retrieve_with_intent(
            "test content", workspace_path=tmp_path,
        )

        assert intent.text == "test content"
        assert isinstance(results, list)

    async def test_empty_query(self):
        from services.retrieval import retrieve_with_intent

        intent, results = await retrieve_with_intent("")
        assert results == []
        assert intent.text == ""
