import pytest

from services.entity_extraction import ExtractedEntity, extract_entities


def test_extract_person_standalone():
    text = "I met with John Smith yesterday about the project."
    entities = extract_entities(text)
    names = [e.text for e in entities if e.type == "person"]
    assert "John Smith" in names


def test_extract_person_contextual():
    text = "I had coffee with Anna Nowak and discussed plans."
    entities = extract_entities(text)
    names = [e.text for e in entities if e.type == "person"]
    assert "Anna Nowak" in names


def test_extract_person_boosted_by_existing():
    text = "Sent email to Jan Kowalski about the deadline."
    entities = extract_entities(text, existing_people=["Jan Kowalski"])
    person = next(e for e in entities if e.text == "Jan Kowalski" and e.type == "person")
    assert person.confidence >= 0.7


def test_extract_date_iso():
    text = "The meeting is on 2026-04-14."
    entities = extract_entities(text)
    dates = [e.text for e in entities if e.type == "date"]
    assert "2026-04-14" in dates


def test_extract_date_natural():
    text = "Let's meet yesterday or tomorrow."
    entities = extract_entities(text)
    dates = [e.text for e in entities if e.type == "date"]
    assert "yesterday" in dates
    assert "tomorrow" in dates


def test_extract_project():
    text = "Working on Project: Apollo for the next quarter."
    entities = extract_entities(text)
    projects = [e.text for e in entities if e.type == "project"]
    assert any("Apollo" in p for p in projects)


def test_skip_common_words():
    text = "The Monday meeting was about This and That."
    entities = extract_entities(text)
    names = [e.text for e in entities if e.type == "person"]
    assert "This" not in names
    assert "That" not in names


def test_dedup_entities():
    text = "John Smith met John Smith again."
    entities = extract_entities(text)
    person_johns = [e for e in entities if e.text == "John Smith" and e.type == "person"]
    assert len(person_johns) == 1


def test_empty_text():
    entities = extract_entities("")
    assert entities == []


def test_no_entities_in_plain_text():
    text = "this is all lowercase without any names or dates"
    entities = extract_entities(text)
    persons = [e for e in entities if e.type == "person"]
    assert len(persons) == 0
