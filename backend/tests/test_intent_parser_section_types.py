"""Tests for intent_parser section-type detection (step 28d)."""
import pytest

from services.retrieval.intent_parser import parse_intent


def test_risks_query_en():
    """'what risks...' query returns preferred_section_types containing 'risks'."""
    intent = parse_intent("what risks does the OWASP document list?")
    assert "risks" in intent.preferred_section_types


def test_requirements_polish():
    """Polish 'jakie wymagania ma klient' maps to requirements."""
    intent = parse_intent("jakie wymagania ma klient w tym dokumencie?")
    assert "requirements" in intent.preferred_section_types


def test_generic_query_empty_section_types():
    """Generic question returns empty preferred_section_types."""
    intent = parse_intent("summarize this document")
    assert intent.preferred_section_types == []


def test_integrations_query():
    """Polish integrations query maps to integrations."""
    intent = parse_intent("co dokument mówi o integracjach z zewnętrznymi systemami?")
    assert "integrations" in intent.preferred_section_types


def test_timeline_query():
    """Timeline query maps to timeline."""
    intent = parse_intent("what is the project timeline and milestones?")
    assert "timeline" in intent.preferred_section_types


def test_multiple_types_detected():
    """'security requirements' detects at least one of security or requirements."""
    intent = parse_intent("what are the security requirements in this RFP?")
    types = set(intent.preferred_section_types)
    assert "security" in types or "requirements" in types


def test_pricing_polish():
    """Polish pricing query maps to pricing."""
    intent = parse_intent("ile to kosztuje i jaka jest wycena?")
    assert "pricing" in intent.preferred_section_types


def test_preferred_types_is_list():
    """preferred_section_types is always a list, never None."""
    intent = parse_intent("hello")
    assert isinstance(intent.preferred_section_types, list)
