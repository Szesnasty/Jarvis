"""Comprehensive Polish language entity extraction tests.

Tests entity extraction quality for Polish text — the primary language
for Jarvis personal knowledge system. Tests cover:

1. Basic person name extraction (nominative forms)
2. Polish declension handling (all 7 cases)
3. Single first names
4. False positive resistance (Polish-specific)
5. Organization extraction
6. Date extraction (Polish formats)
7. Mixed PL/EN text
8. Edge cases (diacritics, compound names, etc.)
9. Lemmatization / normalization of declined names

Each test documents EXPECTED behavior for a killer NER feature.
"""

import pytest

from services.entity_extraction import ExtractedEntity, extract_entities

# Tests marked xfail document desired NER behavior that the small spaCy
# model (pl_core_news_sm) cannot reliably deliver yet.
# They track improvement without blocking CI.
_xfail_ner = pytest.mark.xfail(reason="spaCy sm model NER limitation", strict=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _persons(entities: list[ExtractedEntity]) -> list[str]:
    """Extract person names from entity list."""
    return [e.text for e in entities if e.type == "person"]


def _persons_above_threshold(entities: list[ExtractedEntity], threshold: float = 0.5) -> list[str]:
    """Extract person names above confidence threshold (graph threshold)."""
    return [e.text for e in entities if e.type == "person" and e.confidence >= threshold]


def _orgs(entities: list[ExtractedEntity]) -> list[str]:
    """Extract organization names."""
    return [e.text for e in entities if e.type == "organization"]


def _dates(entities: list[ExtractedEntity]) -> list[str]:
    """Extract dates."""
    return [e.text for e in entities if e.type == "date"]


def _projects(entities: list[ExtractedEntity]) -> list[str]:
    """Extract project names."""
    return [e.text for e in entities if e.type == "project"]


# ===================================================================
# 1. BASIC POLISH PERSON EXTRACTION (nominative forms)
# ===================================================================

class TestPolishBasicPersons:
    """Two-word Polish names in nominative — the easy case."""

    @_xfail_ner
    def test_male_name_nominative(self):
        entities = extract_entities("Adam Nowak jest moim mentorem biznesowym.")
        assert "Adam Nowak" in _persons_above_threshold(entities)

    @_xfail_ner
    def test_female_name_nominative(self):
        entities = extract_entities("Anna Kowalska prowadzi spotkanie.")
        assert "Anna Kowalska" in _persons_above_threshold(entities)

    @_xfail_ner
    def test_multiple_persons(self):
        entities = extract_entities(
            "Michał Kowalski i Marek Wiśniewski pracują razem nad projektem."
        )
        names = _persons_above_threshold(entities)
        assert "Michał Kowalski" in names
        assert "Marek Wiśniewski" in names

    @_xfail_ner
    def test_person_with_context_boost(self):
        """Known person should get higher confidence."""
        entities = extract_entities(
            "Spotkanie z Adamem Nowakiem.",
            existing_people=["Adam Nowak"],
        )
        persons = [e for e in entities if e.type == "person"]
        # At least one person entity should have boosted confidence
        assert any(e.confidence >= 0.7 for e in persons)

    def test_foreign_name_in_polish_text(self):
        """Foreign names in Polish text should be extracted."""
        entities = extract_entities("Przeczytałem artykuł Sama Altmana o AI.")
        persons = _persons(entities)
        assert any("Altman" in p for p in persons)


# ===================================================================
# 2. POLISH DECLENSION HANDLING (the key feature)
# ===================================================================

class TestPolishDeclension:
    """Polish has 7 grammatical cases. Names get declined.
    Entity extraction MUST handle this.

    Cases: mianownik (nom), dopełniacz (gen), celownik (dat),
           biernik (acc), narzędnik (instr), miejscownik (loc),
           wołacz (voc).
    """

    def test_genitive_dopelniacz(self):
        """'Adama Nowaka' (kogo?) → should extract."""
        entities = extract_entities("Wysłać wiadomość do Adama Nowaka.")
        assert any("Adam" in p and "Nowak" in p for p in _persons(entities))

    def test_dative_celownik(self):
        """'Adamowi Nowakowi' (komu?) → should extract."""
        entities = extract_entities("Przekazałem raport Adamowi Nowakowi.")
        assert any("Adam" in p and "Nowak" in p for p in _persons(entities))

    def test_instrumental_narzednik(self):
        """'Michałem Kowalskim' (z kim?) → should extract."""
        entities = extract_entities("Spotkałem się z Michałem Kowalskim na kawie.")
        assert any("Michał" in p and "Kowalski" in p for p in _persons(entities))

    def test_locative_miejscownik(self):
        """'o Michale Kowalskim' (o kim?) → should extract."""
        entities = extract_entities("Rozmawialiśmy o Michale Kowalskim.")
        assert any("Michał" in p or "Michale" in p for p in _persons(entities))

    def test_female_instrumental(self):
        """'z Anią Krawczyk' → should extract."""
        entities = extract_entities("Rozmawiałem z Anią Krawczyk z TechFund.")
        persons = _persons(entities)
        assert any("Krawczyk" in p for p in persons)

    def test_female_genitive(self):
        """'Kasi Zielińskiej' → should extract."""
        entities = extract_entities("Pomoc od Kasi Zielińskiej była nieoceniona.")
        persons = _persons(entities)
        assert any("Kasi" in p or "Zieliński" in p or "Zielińsk" in p for p in persons)

    @_xfail_ner
    def test_declined_form_normalization(self):
        """Declined forms should be normalized to nominative (base) form.
        This is critical for graph deduplication.

        'Adama Nowaka' → should normalize to something that canonicalizes
        with 'Adam Nowak' (either via lemmatization or Jaro-Winkler).
        """
        entities = extract_entities(
            "Wysłać wiadomość do Adama Nowaka.",
            existing_people=["Adam Nowak"],
        )
        # Should either extract as "Adam Nowak" (normalized) or as declined
        # form with high confidence (will be canonicalized by Jaro-Winkler)
        persons = [e for e in entities if e.type == "person"]
        adam_entities = [e for e in persons if "Adam" in e.text or "Nowak" in e.text]
        assert len(adam_entities) >= 1
        # Must have high confidence since we know Adam Nowak
        assert any(e.confidence >= 0.7 for e in adam_entities)


# ===================================================================
# 3. SINGLE POLISH FIRST NAMES
# ===================================================================

class TestPolishSingleNames:
    """Single first names are common in Polish notes.
    'Ola pytała o...', 'Spotkanie z Janem', etc.
    """

    @_xfail_ner
    def test_single_name_known_person(self):
        """Known single name should be extracted with high confidence."""
        entities = extract_entities(
            "Ola pytała o planach wakacyjnych.",
            existing_people=["Ola"],
        )
        persons = [e for e in entities if e.type == "person" and "Ola" in e.text]
        assert len(persons) >= 1
        assert persons[0].confidence >= 0.7

    @_xfail_ner
    def test_single_name_unknown_low_confidence(self):
        """Unknown single name should have lower confidence (unreliable)."""
        entities = extract_entities("Spotkanie z Janem o projekcie.")
        persons = [e for e in entities if e.type == "person" and "Jan" in e.text]
        # Should be extracted but with lower confidence than two-word names
        # (single words are ambiguous without context)
        assert len(persons) >= 1

    @_xfail_ner
    def test_single_name_with_diacritics(self):
        """Polish names with diacritics: Łukasz, Małgosia, Bartek."""
        entities = extract_entities("Łukasz i Małgosia jadą na wakacje.")
        persons = _persons(entities)
        assert any("Łukasz" in p for p in persons)


# ===================================================================
# 4. FALSE POSITIVE RESISTANCE (Polish-specific)
# ===================================================================

class TestPolishFalsePositiveResistance:
    """These are common Polish words/terms that should NOT be
    extracted as persons. This is where quality matters.
    """

    def test_supplement_name(self):
        """'Melatonina' is a supplement, not a person."""
        entities = extract_entities("Melatonina pomaga na sen. Biorę D3.")
        persons = _persons_above_threshold(entities)
        assert "Melatonina" not in persons
        assert "D3" not in persons

    def test_common_nouns_at_sentence_start(self):
        """Polish capitalizes first word of sentence — not a name."""
        entities = extract_entities("Plan na przyszły tydzień. Budżet do zatwierdzenia.")
        persons = _persons_above_threshold(entities)
        # These are common nouns, not people
        for word in ["Plan", "Budżet"]:
            assert word not in persons

    def test_months_not_persons(self):
        """Polish months (marzec, kwiecień...) should not be persons."""
        entities = extract_entities("Marzec był produktywny. W kwietniu odpoczniemy.")
        persons = _persons_above_threshold(entities)
        assert "Marzec" not in persons
        assert "Kwiecień" not in persons

    def test_section_headers_not_persons(self):
        """Note section headers should not be persons."""
        text = """## Postępy
Dobre wyniki w sprincie.

## Kontekst
Projekt idzie zgodnie z planem.

## Suplementy
Lista witamin do kupienia."""
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        for word in ["Postępy", "Kontekst", "Suplementy"]:
            assert word not in persons

    def test_tech_terms_not_persons(self):
        """Tech/product terms should not be persons."""
        text = "Backend jest gotowy. Frontend wymaga poprawek. Claude API działa."
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        for word in ["Backend", "Frontend", "Claude"]:
            assert word not in persons

    def test_polish_verbs_not_persons(self):
        """Polish verbs that start with uppercase (after period) are not persons."""
        text = "Obiecałem Michałowi code review. Przerobić plan na piątek."
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        for word in ["Obiecałem", "Przerobić"]:
            assert word not in persons

    def test_multi_word_junk(self):
        """Entities with newlines, dashes, or control characters are junk."""
        text = "Postępy\n- Marzec: dobrze\n- Kwiecień: lepiej"
        entities = extract_entities(text)
        persons = _persons(entities)
        # No entity should contain newlines
        for p in persons:
            assert "\n" not in p

    def test_day_names_not_persons(self):
        """Polish day names should not be persons."""
        entities = extract_entities("W poniedziałek spotkanie. Piątek wolny.")
        persons = _persons_above_threshold(entities)
        for day in ["Poniedziałek", "Piątek"]:
            assert day not in persons


# ===================================================================
# 5. ORGANIZATION EXTRACTION
# ===================================================================

class TestPolishOrganizations:
    """Organizations are valuable for knowledge graph."""

    @_xfail_ner
    def test_org_in_context(self):
        """Organization should be extracted when mentioned in context."""
        entities = extract_entities("Spotkanie z firmą TechFund o inwestycji.")
        orgs = _orgs(entities)
        assert any("TechFund" in o for o in orgs)

    @_xfail_ner
    def test_known_company(self):
        """Well-known company names."""
        entities = extract_entities("Mój kolega pracuje w Google.")
        orgs = _orgs(entities)
        assert any("Google" in o for o in orgs)


# ===================================================================
# 6. POLISH DATE EXTRACTION
# ===================================================================

class TestPolishDates:
    """Polish date formats and day/month names."""

    def test_iso_date(self):
        entities = extract_entities("Spotkanie zaplanowane na 2026-04-14.")
        dates = _dates(entities)
        assert "2026-04-14" in dates

    def test_polish_day_names(self):
        entities = extract_entities("W poniedziałek i środę mam spotkania.")
        dates = _dates(entities)
        assert any("poniedziałek" in d.lower() for d in dates)
        assert any("środa" in d.lower() or "środę" in d.lower() for d in dates)

    def test_polish_day_sobota(self):
        entities = extract_entities("Trening w sobotę o 10:00.")
        dates = _dates(entities)
        assert any("sobot" in d.lower() for d in dates)


# ===================================================================
# 7. MIXED PL/EN TEXT
# ===================================================================

class TestMixedLanguageText:
    """Notes often mix Polish and English (code terms, foreign names)."""

    def test_english_name_in_polish_text(self):
        """Foreign name in Polish sentence should be extracted."""
        entities = extract_entities("Spotkanie z Johnem Smithem w biurze.")
        persons = _persons(entities)
        assert any("John" in p or "Smith" in p for p in persons)

    def test_polish_name_among_english(self):
        """Polish name in English context should be extracted."""
        entities = extract_entities("The meeting with Michał Kowalski went well.")
        persons = _persons(entities)
        assert any("Michał" in p or "Kowalski" in p for p in persons)

    @_xfail_ner
    def test_code_mixed_with_names(self):
        """Tech terms mixed with real names."""
        text = "Michał robi code review. Sprint planning z Adamem."
        entities = extract_entities(text)
        persons = _persons(entities)
        assert any("Michał" in p for p in persons)
        assert any("Adam" in p for p in persons)
        # Tech terms should not be persons
        assert "Sprint" not in _persons_above_threshold(entities)


# ===================================================================
# 8. POLISH EDGE CASES
# ===================================================================

class TestPolishEdgeCases:
    """Edge cases specific to Polish language."""

    def test_name_with_polish_diacritics(self):
        """Names with ł, ś, ź, ż, ą, ę, ć, ń, ó."""
        entities = extract_entities("Marek Wiśniewski i Łukasz Żółtowski na spotkaniu.")
        persons = _persons(entities)
        assert any("Wiśniewski" in p for p in persons)

    def test_three_word_name(self):
        """Three-part Polish name: 'Jan Andrzej Kowalski'."""
        entities = extract_entities("Jan Andrzej Kowalski przyjedzie jutro.")
        persons = _persons(entities)
        assert any("Kowalski" in p for p in persons)

    def test_title_with_name(self):
        """Prof. or Dr. prefix with name."""
        entities = extract_entities("Prof. Stanisław Nowak wygłosi wykład.")
        persons = _persons(entities)
        assert any("Nowak" in p or "Stanisław" in p for p in persons)

    def test_empty_text(self):
        entities = extract_entities("")
        assert entities == []

    def test_no_names_plain_text(self):
        """Plain lowercase Polish text without names."""
        entities = extract_entities("to jest zwykły tekst bez żadnych imion ani dat")
        persons = _persons(entities)
        assert len(persons) == 0

    def test_frontmatter_does_not_leak(self):
        """Frontmatter YAML should not generate false persons."""
        text = """---
title: Spotkanie z Adamem
tags: [spotkanie, praca]
---

Rozmawialiśmy o projekcie."""
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        # "Adamem" from title might be extracted, that's ok
        # But "tags" and "title" should not be persons
        for word in ["tags", "title"]:
            assert word not in persons


# ===================================================================
# 9. DEDUPLICATION & CONFIDENCE
# ===================================================================

class TestPolishDeduplication:
    """Entity deduplication and confidence scoring."""

    def test_same_name_twice_deduped(self):
        """Same name appearing twice should be deduplicated."""
        text = "Adam Nowak przyszedł. Adam Nowak wyszedł."
        entities = extract_entities(text)
        adam_entities = [e for e in entities if e.type == "person" and "Adam Nowak" in e.text]
        assert len(adam_entities) == 1

    def test_existing_person_higher_confidence(self):
        """Known person should get higher confidence than unknown."""
        text = "Adam Nowak i Jan Kowalski na spotkaniu."
        entities = extract_entities(text, existing_people=["Adam Nowak"])
        adam = next((e for e in entities if "Adam Nowak" in e.text), None)
        jan = next((e for e in entities if "Jan" in e.text and "Kowalski" in e.text), None)
        if adam and jan:
            assert adam.confidence > jan.confidence


# ===================================================================
# 10. PROJECT EXTRACTION (Polish)
# ===================================================================

class TestPolishProjects:
    """Project extraction from Polish text."""

    def test_projekt_keyword(self):
        entities = extract_entities("Pracuję nad Projekt: Jarvis od lutego.")
        projects = _projects(entities)
        assert any("Jarvis" in p for p in projects)


# ===================================================================
# 11. CANONICAL FORM OUTPUT (critical for graph quality)
# ===================================================================

class TestCanonicalFormOutput:
    """When a declined name matches a known person, the output
    should use the canonical (nominative) form so the graph
    doesn't create duplicate nodes.
    """

    @_xfail_ner
    def test_instrumental_to_canonical(self):
        """'z Michałem Kowalskim' → output 'Michał Kowalski'."""
        entities = extract_entities(
            "Rozmowa z Michałem Kowalskim o projekcie.",
            existing_people=["Michał Kowalski"],
        )
        names = _persons_above_threshold(entities)
        assert "Michał Kowalski" in names

    @_xfail_ner
    def test_genitive_to_canonical(self):
        """'Adama Nowaka' → output 'Adam Nowak'."""
        entities = extract_entities(
            "Wysłać raport do Adama Nowaka.",
            existing_people=["Adam Nowak"],
        )
        names = _persons_above_threshold(entities)
        assert "Adam Nowak" in names

    @_xfail_ner
    def test_dative_to_canonical(self):
        """'Markowi Wiśniewskiemu' → output 'Marek Wiśniewski'."""
        entities = extract_entities(
            "Przekazać zdjęcia Markowi Wiśniewskiemu.",
            existing_people=["Marek Wiśniewski"],
        )
        names = _persons_above_threshold(entities)
        assert "Marek Wiśniewski" in names

    @_xfail_ner
    def test_single_declined_to_canonical(self):
        """'Ewie' → output 'Ewa' when known."""
        entities = extract_entities(
            "Powiedziałem o tym Ewie wczoraj.",
            existing_people=["Ewa"],
        )
        names = _persons_above_threshold(entities)
        assert "Ewa" in names

    @_xfail_ner
    def test_single_genitive_to_canonical(self):
        """'Ani' → output 'Ania' when known."""
        entities = extract_entities(
            "Wysłać raport do Ani.",
            existing_people=["Ania"],
        )
        names = _persons_above_threshold(entities)
        assert "Ania" in names

    @_xfail_ner
    def test_canonical_keeps_casing(self):
        """Canonical form should preserve original casing from existing_people."""
        entities = extract_entities(
            "Spotkanie z Michałem Kowalskim.",
            existing_people=["Michał Kowalski"],
        )
        person = next(
            (e for e in entities if e.type == "person" and e.confidence >= 0.5),
            None,
        )
        assert person is not None
        assert person.text == "Michał Kowalski"

    @_xfail_ner
    def test_unknown_declined_uses_lemma(self):
        """Unknown declined name should use lemmatized form (best effort)."""
        entities = extract_entities("Spotkanie z Pawłem Zielińskim.")
        names = _persons_above_threshold(entities)
        # Should try to lemmatize "Pawłem Zielińskim" to something closer
        # to nominative. At minimum, it must be extracted.
        assert len(names) >= 1
        assert any("Paweł" in n or "Pawłem" in n or "Zieliński" in n for n in names)


# ===================================================================
# 12. SINGLE DECLINED NAME MATCHING (the hard case)
# ===================================================================

class TestSingleDeclinedNameMatching:
    """Polish notes often use just first names in declined forms.
    'Wysłać do Ani', 'Spotkanie z Kasią', 'Porozmawiać z Tomkiem'.
    These MUST match known people.
    """

    @_xfail_ner
    def test_ani_matches_ania(self):
        entities = extract_entities(
            "Wysłać raport do Ani.",
            existing_people=["Ania"],
        )
        names = _persons_above_threshold(entities)
        assert "Ania" in names

    @_xfail_ner
    def test_kasia_matches_kasia(self):
        entities = extract_entities(
            "Spotkanie z Kasią o planach.",
            existing_people=["Kasia"],
        )
        names = _persons_above_threshold(entities)
        assert "Kasia" in names

    @_xfail_ner
    def test_tomkiem_matches_tomek(self):
        entities = extract_entities(
            "Na obiedzie z Tomkiem omawialiśmy nowy projekt. Tomek ma ciekawy pomysł.",
            existing_people=["Tomek"],
        )
        names = _persons_above_threshold(entities)
        assert "Tomek" in names

    @_xfail_ner
    def test_marka_matches_marek(self):
        entities = extract_entities(
            "Zadzwonić do Marka po obiedzie.",
            existing_people=["Marek"],
        )
        names = _persons_above_threshold(entities)
        assert "Marek" in names

    @_xfail_ner
    def test_ewy_matches_ewa(self):
        entities = extract_entities(
            "Kupić prezent dla Ewy na urodziny w sobotę. Ewa lubi książki.",
            existing_people=["Ewa"],
        )
        names = _persons_above_threshold(entities)
        assert "Ewa" in names

    @_xfail_ner
    def test_olą_matches_ola(self):
        # Provide longer context — very short sentences may not trigger
        # spaCy's NER at all. This tests that IF detected, it matches.
        entities = extract_entities(
            "W sobotę idziemy z Olą na spacer do parku. Ola lubi dużo chodzić.",
            existing_people=["Ola"],
        )
        names = _persons_above_threshold(entities)
        assert "Ola" in names

    @_xfail_ner
    def test_bartek_instrumental(self):
        # Provide enough context for spaCy to recognize the entity
        entities = extract_entities(
            "Wieczorem piwo z Bartkiem w barze na Mokotowie. Bartek obiecał przyjść o siódmej.",
            existing_people=["Bartek"],
        )
        names = _persons_above_threshold(entities)
        assert "Bartek" in names

    def test_no_match_when_unknown(self):
        """Declined single name should NOT match someone with different stem."""
        entities = extract_entities(
            "Spotkanie z Kasią.",
            existing_people=["Marek"],
        )
        # Kasia should be low-confidence, Marek should NOT appear
        assert "Marek" not in _persons_above_threshold(entities)


# ===================================================================
# 13. FALSE POSITIVE RESISTANCE — TECH/WORK TERMS
# ===================================================================

class TestFalsePositiveTechWork:
    """English tech/work terms that spaCy PL model misclassifies
    as person names. These are CRITICAL false positives to block.
    """

    @_xfail_ner
    def test_review_pr_not_person(self):
        """'Review PR' is NOT a person — it's a work task."""
        entities = extract_entities("Review PR od Marka.", existing_people=["Marek"])
        names = _persons_above_threshold(entities)
        assert "Review PR" not in names
        assert "Marek" in names

    def test_deploy_app_not_person(self):
        entities = extract_entities("Deploy App na produkcję.")
        names = _persons_above_threshold(entities)
        assert not any("Deploy" in n for n in names)

    def test_merge_branch_not_person(self):
        entities = extract_entities("Merge branch feature/auth.")
        names = _persons_above_threshold(entities)
        assert not any("Merge" in n for n in names)

    def test_update_docs_not_person(self):
        entities = extract_entities("Update Docs po deployu.")
        names = _persons_above_threshold(entities)
        assert not any("Update" in n for n in names)

    def test_push_changes_not_person(self):
        entities = extract_entities("Push changes do mastera.")
        names = _persons_above_threshold(entities)
        assert not any("Push" in n for n in names)

    def test_tech_acronyms_not_person(self):
        """Short uppercase acronyms like PR, CI, QA, API are not persons."""
        entities = extract_entities("Sprawdzić PR i uruchomić CI pipeline.")
        names = _persons_above_threshold(entities)
        for acr in ["PR", "CI"]:
            assert acr not in names

    def test_code_review_mixed_with_person(self):
        """Real person name next to tech term."""
        text = "Code review z Michałem. Deploy na staging."
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        assert not any("Deploy" in p for p in persons)


# ===================================================================
# 14. FALSE POSITIVE RESISTANCE — SUPPLEMENTS & HEALTH
# ===================================================================

class TestFalsePositiveSupplements:
    """Supplement names in Polish health notes look like proper names
    because they start with uppercase at sentence start.
    """

    def test_magnez_not_person(self):
        entities = extract_entities("Magnez pomaga na skurcze mięśni.")
        assert "Magnez" not in _persons_above_threshold(entities)

    def test_magnezu_not_person(self):
        """Declined supplement: 'Magnezu' (genitive of Magnez)."""
        entities = extract_entities("Brakuje mi magnezu, trzeba kupić.")
        assert not any("agnez" in p.lower() for p in _persons_above_threshold(entities))

    def test_witamina_not_person(self):
        entities = extract_entities("Witamina D3 i omega-3 codziennie.")
        assert "Witamina" not in _persons_above_threshold(entities)

    def test_ashwagandha_not_person(self):
        entities = extract_entities("Ashwagandha na stres, melatonina na sen.")
        assert "Ashwagandha" not in _persons_above_threshold(entities)
        assert "Melatonina" not in _persons_above_threshold(entities)

    def test_supplement_list_no_persons(self):
        """Full supplement list — none should be persons."""
        text = """Suplementy do kupienia:
- Magnez (cytrynian)
- Witamina D3 + K2
- Omega-3
- Cynk
- Ashwagandha
- Probiotyk"""
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        assert len(persons) == 0


# ===================================================================
# 15. TASK LIST CONTEXT (real use case)
# ===================================================================

class TestTaskListContext:
    """Markdown task lists are the most common format in notes.
    Names appear in tasks like '- [ ] Napisać do Ani'.
    """

    @_xfail_ner
    def test_checkbox_task_with_name(self):
        text = "- [ ] Napisać do Ani o spotkaniu"
        entities = extract_entities(text, existing_people=["Ania"])
        names = _persons_above_threshold(entities)
        assert "Ania" in names

    @_xfail_ner
    def test_completed_task_with_name(self):
        text = "- [x] Spotkanie z Michałem Kowalskim"
        entities = extract_entities(text, existing_people=["Michał Kowalski"])
        names = _persons_above_threshold(entities)
        assert "Michał Kowalski" in names

    @_xfail_ner
    def test_multiple_tasks_multiple_names(self):
        text = """- [ ] Zadzwonić do Marka
- [ ] Mail do Ani
- [x] Spotkanie z Ewą
- [ ] Review z Adamem"""
        entities = extract_entities(
            text,
            existing_people=["Marek", "Ania", "Ewa", "Adam"],
        )
        names = _persons_above_threshold(entities)
        # Should find at least some of the people
        found_count = sum(1 for n in ["Marek", "Ania", "Ewa", "Adam"] if n in names)
        assert found_count >= 2, f"Expected at least 2 people, found: {names}"

    def test_task_no_false_positive_from_verbs(self):
        text = """- [ ] Kupić mleko
- [ ] Napisać raport
- [ ] Sprawdzić wyniki
- [ ] Zamówić książkę"""
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        # None of these tasks contain person names
        assert len(persons) == 0


# ===================================================================
# 16. WEEKLY PLAN / JOURNAL CONTEXT (real use case)
# ===================================================================

class TestWeeklyPlanContext:
    """Full weekly plans with multiple people, dates, projects."""

    @_xfail_ner
    def test_rich_weekly_plan(self):
        text = """# Plan na tydzień (2026-01-12)

## Poniedziałek
- Spotkanie z Michałem Kowalskim o backendzie
- Code review PR od Adama

## Wtorek
- Lunch z Ewą
- Prezentacja dla zarządu

## Środa
- Call z Markiem Wiśniewskim (TechFund)

## Piątek
- Retrospektywa z zespołem
- Piwo z Bartkiem"""
        entities = extract_entities(
            text,
            existing_people=["Michał Kowalski", "Adam Nowak", "Ewa",
                             "Marek Wiśniewski", "Bartek"],
        )
        names = _persons_above_threshold(entities)
        persons_found = 0
        for expected in ["Michał Kowalski", "Ewa", "Marek Wiśniewski", "Bartek"]:
            if expected in names:
                persons_found += 1
        assert persons_found >= 2, f"Expected at least 2 known people, found: {names}"

        # Dates should be extracted
        dates = _dates(entities)
        assert "2026-01-12" in dates

        # "Review PR" should NOT be a person
        assert "Review PR" not in names

    @_xfail_ner
    def test_daily_journal(self):
        text = """# 2026-01-15 Środa

Rano spotkanie z Anią. Omówiliśmy budżet na Q2.
Po obiedzie quick sync z Markiem. Trzeba mu przesłać raport.
Wieczorem trening i potem kolacja z Kasią.

## TODO
- Odpowiedzieć Michałowi
- Wysłać fakturę do Kasi
- Zamówić magnez i omega-3"""
        entities = extract_entities(
            text,
            existing_people=["Ania", "Marek", "Kasia", "Michał"],
        )
        names = _persons_above_threshold(entities)
        found = sum(1 for n in ["Ania", "Marek", "Kasia", "Michał"] if n in names)
        assert found >= 2, f"Expected at least 2 people from daily journal, found: {names}"
        # Supplements should not be persons
        assert "Magnez" not in _persons_above_threshold(entities)

    def test_meeting_notes(self):
        text = """# Spotkanie z zespołem — 2026-01-20

Uczestnicy: Adam Nowak, Ewa Malinowska, Tomek Zieliński

Omówiliśmy plan na następny sprint. Adam przedstawił nowy design.
Ewa zgłosiła problemy z CI pipeline. Tomek pracuje nad API."""
        entities = extract_entities(
            text,
            existing_people=["Adam Nowak", "Ewa Malinowska", "Tomek Zieliński"],
        )
        names = _persons_above_threshold(entities)
        found = sum(1 for n in ["Adam Nowak", "Ewa Malinowska", "Tomek Zieliński"]
                     if n in names)
        assert found >= 2, f"Expected at least 2 people in meeting notes, found: {names}"


# ===================================================================
# 17. TRAVEL NOTES (places ≠ persons)
# ===================================================================

class TestTravelNotesContext:
    """Travel notes mention many place names that should NOT
    be extracted as persons.
    """

    def test_cities_not_persons(self):
        text = "Lot do Tokio w maju. Potem Kioto na 3 dni."
        entities = extract_entities(text)
        persons = _persons_above_threshold(entities)
        for city in ["Tokio", "Kioto"]:
            assert city not in persons

    @_xfail_ner
    def test_travel_with_people(self):
        text = "Podróż z Kasią do Barcelony. Wracamy przez Paryż."
        entities = extract_entities(text, existing_people=["Kasia"])
        names = _persons_above_threshold(entities)
        assert "Kasia" in names
        assert "Barcelona" not in names and "Barcelony" not in names
        assert "Paryż" not in names


# ===================================================================
# 18. FORMAL TITLES & PROFESSIONAL CONTEXT
# ===================================================================

class TestFormalTitles:
    """Polish notes may use formal references: Pan/Pani, Dr., Prof."""

    def test_pan_with_surname(self):
        """'Pan Jankowski' — should extract the name."""
        entities = extract_entities("Spotkanie z Panem Jankowskim o umowie.")
        persons = _persons(entities)
        assert any("Jankowski" in p or "Jankowskim" in p for p in persons)

    @_xfail_ner
    def test_dr_with_name(self):
        """'dr Marka Nowaka' — should find the person."""
        entities = extract_entities(
            "Wizyta u dr. Marka Nowaka w czwartek.",
            existing_people=["Marek Nowak"],
        )
        names = _persons_above_threshold(entities)
        assert "Marek Nowak" in names

    def test_prof_with_name(self):
        entities = extract_entities("Wykład prof. Stanisława Kowalskiego.")
        persons = _persons(entities)
        assert any("Kowalski" in p or "Stanisław" in p for p in persons)


# ===================================================================
# 19. FOREIGN AUTHORS IN POLISH TEXT
# ===================================================================

class TestForeignAuthorsInPolish:
    """Polish notes about books/articles often mention foreign authors
    in declined forms: 'książka Yuvala Harariego'.
    """

    @_xfail_ner
    def test_foreign_author_declined(self):
        """Yuval Harari in Polish genitive: 'Yuvala Harariego'.
        EN model should detect and fuzzy-match to known person."""
        entities = extract_entities(
            "Czytam nową książkę Yuvala Harariego o przyszłości ludzkości.",
            existing_people=["Yuval Harari"],
        )
        names = _persons_above_threshold(entities)
        assert "Yuval Harari" in names

    def test_foreign_author_nominative(self):
        entities = extract_entities("James Clear napisał 'Atomowe nawyki'.")
        persons = _persons(entities)
        assert any("James" in p and "Clear" in p for p in persons)

    @_xfail_ner
    def test_multiple_foreign_authors(self):
        text = "Porównuję podejścia Petera Thiela i Bena Horowitza."
        entities = extract_entities(
            text,
            existing_people=["Peter Thiel", "Ben Horowitz"],
        )
        names = _persons_above_threshold(entities)
        found = sum(1 for n in ["Peter Thiel", "Ben Horowitz"] if n in names)
        assert found >= 1, f"Expected at least 1 foreign author, found: {names}"


# ===================================================================
# 20. MULTI-ENTITY DEDUPLICATION (advanced)
# ===================================================================

class TestAdvancedDeduplication:
    """When the same person appears in different forms within one text."""

    @_xfail_ner
    def test_nom_and_declined_same_person(self):
        """'Adam Nowak' and 'Adama Nowaka' in same text.
        EN model should not re-add a duplicate of an already-found entity."""
        text = """Adam Nowak poprowadzi warsztaty.
Po warsztacie pogadam z Adamem Nowakiem o wynikach."""
        entities = extract_entities(text, existing_people=["Adam Nowak"])
        adam_above = [e for e in entities
                      if e.type == "person" and "Adam" in e.text and e.confidence >= 0.5]
        # Should be deduplicated to single high-confidence entity
        assert len(adam_above) == 1
        assert adam_above[0].text == "Adam Nowak"
        assert adam_above[0].confidence >= 0.8

    def test_first_name_and_full_name(self):
        """'Michał' and 'Michał Kowalski' in same text."""
        text = "Michał Kowalski prowadzi daily. Potem Michał idzie na lunch."
        entities = extract_entities(text, existing_people=["Michał Kowalski"])
        persons = _persons_above_threshold(entities)
        # Both should resolve to "Michał Kowalski"
        michal_count = sum(1 for p in persons if "Michał" in p)
        assert michal_count >= 1

    @_xfail_ner
    def test_three_forms_same_person(self):
        """Person mentioned in 3 different cases."""
        text = """Ewa jest bardzo pomocna.
Zadzwoniłem do Ewy rano.
Spotkanie z Ewą po południu."""
        entities = extract_entities(text, existing_people=["Ewa"])
        ewa_entities = [e for e in entities if e.type == "person" and "Ewa" in e.text]
        assert len(ewa_entities) >= 1
        assert all(e.text == "Ewa" for e in ewa_entities)


# ===================================================================
# 21. CONFIDENCE SCORING (correctness)
# ===================================================================

class TestConfidenceScoring:
    """Verify confidence levels match expected logic."""

    def test_known_person_high_confidence(self):
        entities = extract_entities(
            "Spotkanie z Adamem.", existing_people=["Adam"]
        )
        adam = next((e for e in entities if e.type == "person" and "Adam" in e.text), None)
        if adam:
            assert adam.confidence >= 0.8

    def test_unknown_multiword_medium_confidence(self):
        entities = extract_entities("Spotkanie z Pawłem Nowakiem.")
        pawel = next(
            (e for e in entities if e.type == "person" and "Paweł" in e.text or "Nowak" in e.text),
            None,
        )
        if pawel:
            assert 0.4 <= pawel.confidence <= 0.7

    def test_unknown_single_word_low_confidence(self):
        entities = extract_entities("Spotkanie z Bartkiem.")
        bartek = next(
            (e for e in entities if e.type == "person" and "Bart" in e.text),
            None,
        )
        if bartek:
            assert bartek.confidence < 0.5

    def test_org_medium_confidence(self):
        entities = extract_entities("Pracuję dla Google od roku.")
        org = next((e for e in entities if e.type == "organization"), None)
        if org:
            assert 0.3 <= org.confidence <= 0.6


# ===================================================================
# 22. SENTENCE-INITIAL WORDS NOT PERSONS
# ===================================================================

class TestSentenceInitialWords:
    """Words at the start of a sentence are capitalized in Polish.
    They should NOT be misclassified as persons.
    """

    def test_common_nouns_at_start(self):
        texts = [
            "Trening o 7 rano.",
            "Dieta wymaga poprawek.",
            "Urlop od 1 do 15 marca.",
            "Praca nad projektem idzie dobrze.",
            "Spotkanie przełożone na piątek.",
            "Raport wysłany do klienta.",
        ]
        for text in texts:
            entities = extract_entities(text)
            persons = _persons_above_threshold(entities)
            first_word = text.split()[0]
            assert first_word not in persons, f"'{first_word}' misclassified as person in: {text}"

    def test_imperative_verbs_at_start(self):
        """Polish imperatives like 'Kupić', 'Napisać' start with uppercase."""
        texts = [
            "Kupić mleko i chleb.",
            "Napisać raport kwartalny.",
            "Sprawdzić wyniki testów.",
            "Zamówić nowy laptop.",
        ]
        for text in texts:
            entities = extract_entities(text)
            persons = _persons_above_threshold(entities)
            first_word = text.split()[0]
            assert first_word not in persons, f"'{first_word}' misclassified as person in: {text}"
