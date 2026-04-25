"""Tests for document_classifier.py (step 28d)."""
import pytest

from services.document_classifier import (
    SECTION_TYPES,
    classify_section_heuristic,
)


def test_risks_heading_and_body():
    """Heading 'Ryzyka' + body with threat language returns risks with conf >= 0.7."""
    stype, conf, _ = classify_section_heuristic(
        "Ryzyka",
        "Główne ryzyka projektu obejmują zagrożenia bezpieczeństwa oraz podatności w systemie. "
        "Każde ryzyko zostało ocenione pod kątem prawdopodobieństwa i wpływu.",
    )
    assert stype == "risks", f"Expected 'risks', got '{stype}'"
    assert conf >= 0.7, f"Expected conf ≥ 0.7, got {conf}"


def test_generic_introduction_stage1_returns_other():
    """Generic 'Introduction' heading with neutral body → Stage 1 returns 'other'."""
    stype, conf, _ = classify_section_heuristic(
        "Introduction",
        "This document provides an overview of the project.",
    )
    # Short or generic → heuristic defers
    assert stype == "other"


def test_low_margin_returns_other():
    """Body with equal signals for multiple types → confidence/margin too low → other."""
    body = (
        "This section covers requirements, risks, integrations, timeline, pricing, "
        "and stakeholders equally, with no single dominant signal."
    )
    stype, conf, _ = classify_section_heuristic("Mixed Section", body)
    # When margin between top-2 is < 0.15, we expect 'other'
    assert stype == "other"


def test_pl_requirements_heading_and_body():
    """Polish 'Wymagania' heading → requirements, even with mixed EN/PL body."""
    stype, conf, _ = classify_section_heuristic(
        "Wymagania",
        "System musi spełniać następujące wymagania: shall support OAuth2, "
        "must provide REST API, wymagany jest eksport do CSV.",
    )
    assert stype == "requirements", f"Expected 'requirements', got '{stype}'"
    assert conf >= 0.6


def test_all_types_in_taxonomy():
    """SECTION_TYPES list contains the 12 expected canonical types."""
    expected = {
        "requirements", "risks", "integrations", "security", "timeline",
        "pricing", "stakeholders", "open_questions", "technical_constraints",
        "business_goals", "front_matter", "other",
    }
    assert set(SECTION_TYPES) == expected


def test_security_body_recognised():
    """Body with auth + encryption + RBAC → security type."""
    stype, conf, _ = classify_section_heuristic(
        "Security Model",
        "Authentication uses JWT tokens. Authorization enforces RBAC policies. "
        "All data is encrypted in transit via TLS 1.3.",
    )
    assert stype == "security", f"Expected 'security', got '{stype}'"


def test_pricing_polish_heading():
    """'Cennik' heading → pricing."""
    stype, conf, _ = classify_section_heuristic(
        "Cennik",
        "Koszt wdrożenia systemu wynosi 120 000 PLN. Budżet na utrzymanie to 20 000 PLN rocznie.",
    )
    assert stype == "pricing", f"Expected 'pricing', got '{stype}'"


def test_empty_body_returns_other():
    """Empty body should not crash and returns 'other' with low confidence."""
    stype, conf, _ = classify_section_heuristic("Section", "")
    assert stype == "other"
    assert isinstance(conf, float)
