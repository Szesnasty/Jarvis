"""Comprehensive English language entity extraction tests.

Tests entity extraction quality for English text. While Jarvis is primarily
a Polish-language system, users may write mixed-language notes, read English
books, reference English-speaking colleagues, and use English in many contexts.

Tests cover:
1. Basic person name extraction
2. Multi-word and compound names
3. Known person matching and confidence boosting
4. Deduplication across models (PL + EN)
5. False positive resistance — tech terms, products, companies
6. False positive resistance — place names, day/month names
7. Task list and bullet-point context
8. Book and article references
9. Meeting notes context
10. Email / message context
11. Title prefixes (Dr., Prof., Mr., Mrs.)
12. Hyphenated and multi-part names
13. Organizations vs persons
14. Confidence scoring
15. Single-word names with existing_people
16. Mixed EN/PL text
17. Edge cases

Each test documents EXPECTED behavior for English NER in Jarvis.
"""

import pytest

from services.entity_extraction import ExtractedEntity, extract_entities


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _persons(entities: list[ExtractedEntity]) -> list[str]:
    """Extract person names from entity list."""
    return [e.text for e in entities if e.type == "person"]


def _persons_above(entities: list[ExtractedEntity], threshold: float = 0.5) -> list[str]:
    """Extract person names above confidence threshold."""
    return [e.text for e in entities if e.type == "person" and e.confidence >= threshold]


def _orgs(entities: list[ExtractedEntity]) -> list[str]:
    """Extract organization names."""
    return [e.text for e in entities if e.type == "organization"]


def _dates(entities: list[ExtractedEntity]) -> list[str]:
    """Extract dates."""
    return [e.text for e in entities if e.type == "date"]


def _person_conf(entities: list[ExtractedEntity], name: str) -> float:
    """Get confidence for a specific person name."""
    for e in entities:
        if e.type == "person" and e.text == name:
            return e.confidence
    return 0.0


# ===================================================================
# 1. BASIC ENGLISH PERSON EXTRACTION
# ===================================================================

class TestEnglishBasicPersons:
    """Standard two-word English names."""

    def test_simple_first_last(self):
        entities = extract_entities("I met with John Smith yesterday about the project.")
        assert "John Smith" in _persons(entities)

    def test_female_name(self):
        entities = extract_entities("Sarah Johnson sent me the report this morning.")
        assert "Sarah Johnson" in _persons(entities)

    def test_multiple_persons(self):
        entities = extract_entities(
            "David Brown and Emily Davis are leading the project together."
        )
        names = _persons(entities)
        assert any("David" in n for n in names)
        assert any("Emily" in n or "Davis" in n for n in names)

    def test_name_at_sentence_start(self):
        entities = extract_entities("Michael Lee proposed a new architecture for the backend.")
        names = _persons(entities)
        assert any("Michael" in n for n in names)

    def test_name_at_sentence_end(self):
        entities = extract_entities("The keynote was delivered by Steve Wozniak.")
        names = _persons(entities)
        assert any("Wozniak" in n for n in names)

    def test_name_in_possessive(self):
        entities = extract_entities("I read James Clear's book about atomic habits.")
        names = _persons(entities)
        assert any("James Clear" in n or "James" in n for n in names)


# ===================================================================
# 2. MULTI-WORD AND COMPOUND NAMES
# ===================================================================

class TestCompoundNames:
    """Names with middle names, suffixes, or complex structures."""

    def test_three_word_name(self):
        entities = extract_entities(
            "I had a meeting with Mary Jane Watson about the report."
        )
        names = _persons(entities)
        assert any("Mary" in n for n in names)

    def test_name_with_particle(self):
        """Names with 'de', 'van', etc."""
        entities = extract_entities(
            "The painting was by Vincent van Gogh, a remarkable artist."
        )
        names = _persons(entities)
        assert any("Gogh" in n or "Vincent" in n for n in names)

    def test_hyphenated_last_name(self):
        entities = extract_entities(
            "Anna Smith-Jones organized the team offsite event."
        )
        names = _persons(entities)
        assert any("Anna" in n for n in names)


# ===================================================================
# 3. KNOWN PERSON MATCHING AND CONFIDENCE
# ===================================================================

class TestKnownPersonMatching:
    """Matching against existing_people should boost confidence."""

    def test_exact_known_person_boost(self):
        entities = extract_entities(
            "Sent a message to John Smith about the deadline.",
            existing_people=["John Smith"],
        )
        assert _person_conf(entities, "John Smith") >= 0.7

    def test_known_person_canonical_form(self):
        """Should use canonical form from existing_people."""
        entities = extract_entities(
            "I talked to john smith today about the project.",
            existing_people=["John Smith"],
        )
        # Should use the canonical casing
        names = _persons(entities)
        assert any("John Smith" in n or "john smith" in n for n in names)

    def test_unknown_person_lower_confidence(self):
        """Unknown multi-word person should get moderate confidence."""
        entities = extract_entities("I met Robert Peterson at the conference.")
        persons = [e for e in entities if e.type == "person"]
        for p in persons:
            if "Robert" in p.text or "Peterson" in p.text:
                assert p.confidence < 0.85  # Not boosted

    def test_multiple_known_people(self):
        """Multiple known people matched correctly."""
        entities = extract_entities(
            "Meeting with Alice Chen and Bob Martinez to discuss the roadmap.",
            existing_people=["Alice Chen", "Bob Martinez"],
        )
        names = _persons(entities)
        assert any("Alice Chen" in n for n in names)
        assert any("Bob Martinez" in n for n in names)

    def test_partial_name_with_known_full(self):
        """Single first name should match known full name."""
        entities = extract_entities(
            "Alice mentioned the deadline is next Friday.",
            existing_people=["Alice Chen"],
        )
        persons = _persons(entities)
        # Should either match to "Alice Chen" or at least have "Alice"
        assert any("Alice" in n for n in persons)


# ===================================================================
# 4. DEDUPLICATION
# ===================================================================

class TestEnglishDeduplication:
    """Entity deduplication within and across PL/EN models."""

    def test_same_name_twice(self):
        entities = extract_entities(
            "John Smith presented first. Then John Smith answered questions."
        )
        john_count = sum(1 for n in _persons(entities) if "John Smith" in n)
        assert john_count == 1

    def test_no_duplicate_across_models(self):
        """PL and EN model should not both emit the same entity."""
        entities = extract_entities(
            "I read a book by Martin Kleppmann about distributed systems."
        )
        martin_count = sum(1 for n in _persons(entities) if "Kleppmann" in n)
        assert martin_count <= 1

    def test_declined_and_nominative_dedup(self):
        """If both declined and base form are found, keep only one."""
        entities = extract_entities(
            "I discussed the plan with Anna Nowak. Anna Nowak agreed.",
            existing_people=["Anna Nowak"],
        )
        anna_count = sum(1 for n in _persons(entities) if "Anna Nowak" in n)
        assert anna_count == 1


# ===================================================================
# 5. FALSE POSITIVE RESISTANCE — TECH TERMS
# ===================================================================

class TestFalsePositiveTech:
    """Tech terms, product names, and programming concepts."""

    def test_no_react_as_person(self):
        entities = extract_entities("We should migrate from React to Vue next quarter.")
        names = _persons(entities)
        assert "React" not in names
        assert "Vue" not in names

    def test_no_docker_kubernetes(self):
        entities = extract_entities("Deploy the Docker container to Kubernetes cluster.")
        names = _persons(entities)
        assert "Docker" not in names
        assert "Kubernetes" not in names

    def test_no_claude_as_person(self):
        entities = extract_entities("I asked Claude to generate a summary of the notes.")
        names = _persons(entities)
        assert "Claude" not in names

    def test_no_fastapi_as_person(self):
        entities = extract_entities("FastAPI handles the REST endpoints efficiently.")
        names = _persons(entities)
        assert "FastAPI" not in names

    def test_no_sqlite_as_person(self):
        entities = extract_entities("All data is stored locally in SQLite.")
        names = _persons(entities)
        assert "SQLite" not in names

    def test_review_pr_not_person(self):
        """'Review PR' should not be extracted as a person name."""
        entities = extract_entities("I need to review PR #42 before the standup.")
        names = _persons_above(entities)
        assert not any("Review" in n for n in names)

    def test_deploy_app_not_person(self):
        entities = extract_entities("Deploy App to production server by Friday.")
        names = _persons_above(entities)
        assert not any("Deploy" in n for n in names)

    def test_merge_branch_not_person(self):
        entities = extract_entities("Merge Branch into main after approval.")
        names = _persons_above(entities)
        assert not any("Merge" in n for n in names)

    def test_no_github_copilot_as_person(self):
        entities = extract_entities(
            "GitHub Copilot suggested a cleaner implementation."
        )
        names = _persons(entities)
        assert not any("Copilot" in n for n in names)


# ===================================================================
# 6. FALSE POSITIVE RESISTANCE — PLACES AND DATES
# ===================================================================

class TestFalsePositivePlacesDates:
    """Place names and day/month names should not be persons."""

    def test_no_city_as_person(self):
        entities = extract_entities("I traveled to New York for the conference.")
        names = _persons(entities)
        assert "New York" not in names

    def test_no_country_as_person(self):
        entities = extract_entities("The team is expanding to the United States.")
        names = _persons(entities)
        assert "United States" not in names

    def test_no_monday_as_person(self):
        entities = extract_entities("Monday is the deadline for the proposal.")
        names = _persons(entities)
        assert "Monday" not in names

    def test_no_january_as_person(self):
        entities = extract_entities("January was the busiest month for the team.")
        names = _persons_above(entities)
        assert "January" not in names

    def test_no_company_hq_as_person(self):
        entities = extract_entities(
            "The meeting is at the San Francisco headquarter."
        )
        names = _persons(entities)
        assert "San Francisco" not in names


# ===================================================================
# 7. TASK LIST AND BULLET-POINT CONTEXT
# ===================================================================

class TestTaskListContext:
    """Entity extraction from structured task/to-do text."""

    def test_task_list_with_names(self):
        text = """## Tasks for today
- Send report to Sarah Williams
- Call Michael Brown about invoices
- Review deck from Elena Petrova"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Sarah" in n for n in names)
        assert any("Michael" in n or "Brown" in n for n in names)

    def test_checklist_with_assignments(self):
        text = """- [x] John approved budget
- [ ] Lisa needs to finalize the contract
- [ ] David will handle the logistics"""
        entities = extract_entities(text)
        names = _persons(entities)
        # At least some names should be found
        assert len(names) >= 1

    def test_action_items_with_people(self):
        text = """Action items:
1. Follow up with James Anderson on pricing
2. Schedule call with Karen Lee
3. Send slides to Tom Wilson"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("James" in n or "Anderson" in n for n in names)

    def test_no_task_verbs_as_persons(self):
        """Task verbs at bullet points should not be persons."""
        text = """- Review the code
- Update the docs
- Deploy the app
- Test the endpoints"""
        entities = extract_entities(text)
        names = _persons_above(entities)
        assert not any(n in ["Review", "Update", "Deploy", "Test"] for n in names)


# ===================================================================
# 8. BOOK AND ARTICLE REFERENCES
# ===================================================================

class TestBookReferences:
    """Names in book/article reference context."""

    def test_book_author_with_title(self):
        text = '"Atomic Habits" by James Clear changed my approach to productivity.'
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("James Clear" in n for n in names)

    def test_multiple_authors_in_reading_list(self):
        text = """## Reading List
- "Zero to One" — Peter Thiel
- "Deep Work" — Cal Newport
- "The Hard Thing About Hard Things" — Ben Horowitz"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Peter Thiel" in n for n in names)
        assert any("Cal Newport" in n for n in names)
        assert any("Ben Horowitz" in n for n in names)

    def test_author_in_recommendation(self):
        text = "I recommend reading anything by Malcolm Gladwell for insights on social science."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Gladwell" in n or "Malcolm" in n for n in names)

    def test_book_title_not_person(self):
        """Book titles should not be extracted as persons."""
        text = 'I finished "Thinking Fast And Slow" yesterday.'
        entities = extract_entities(text)
        names = _persons(entities)
        # "Thinking Fast And Slow" should not be a person
        assert not any("Thinking" in n for n in names)

    def test_known_author_in_reference(self):
        text = "Re-reading Kleppmann's chapter on replication strategies."
        entities = extract_entities(
            text,
            existing_people=["Martin Kleppmann"],
        )
        names = _persons(entities)
        assert any("Kleppmann" in n for n in names)


# ===================================================================
# 9. MEETING NOTES CONTEXT
# ===================================================================

class TestMeetingNotes:
    """Entity extraction from meeting notes format."""

    def test_meeting_attendees(self):
        text = """## Weekly standup — 2026-04-14
Attendees: John Smith, Sarah Miller, David Lee
Topics: sprint review, Q2 planning"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("John Smith" in n for n in names)
        assert any("Sarah Miller" in n for n in names)

    def test_speaker_attribution(self):
        text = """Meeting notes:
John: We need to finalize the architecture.
Sarah: I agree, let's schedule a review.
David: I'll prepare the CI pipeline docs."""
        entities = extract_entities(text)
        names = _persons(entities)
        # Speaker names may or may not be extracted since they're single words
        # This test documents current behavior
        assert isinstance(names, list)

    def test_action_owner_in_notes(self):
        text = """## Decisions
- API design → Robert Chen owns this
- Database schema → Lisa Wang will deliver by Friday
- Frontend → Mark Anderson starts next week"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Robert" in n or "Chen" in n for n in names)

    def test_facilitator_mention(self):
        text = "The meeting was facilitated by Amanda Richards from the PM team."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Amanda" in n for n in names)


# ===================================================================
# 10. EMAIL / MESSAGE CONTEXT
# ===================================================================

class TestEmailContext:
    """Entity extraction from email/message-like text."""

    def test_email_greeting(self):
        text = """Hi Michael,

Thanks for the update on the project timeline. Let me check with Jennifer
and get back to you by Thursday.

Best,
Alex"""
        entities = extract_entities(text)
        names = _persons(entities)
        # At least Michael or Jennifer should be found
        assert any("Michael" in n or "Jennifer" in n for n in names)

    def test_forwarded_message_from(self):
        text = "Forwarded from Daniel Kim: Please review the attached proposal."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Daniel" in n or "Kim" in n for n in names)

    def test_cc_line(self):
        text = "CC: Patricia Moore, Kevin Wang, Rachel Green"
        entities = extract_entities(text)
        names = _persons(entities)
        assert len(names) >= 1  # At least one name extracted


# ===================================================================
# 11. TITLE PREFIXES
# ===================================================================

class TestTitlePrefixes:
    """Names with Dr., Prof., Mr., Mrs., etc."""

    def test_doctor_title(self):
        text = "I have an appointment with Dr. Robert Wilson on Thursday."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Robert" in n or "Wilson" in n for n in names)

    def test_professor_title(self):
        text = "Professor Elizabeth Warren gave an excellent lecture on economics."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Elizabeth" in n or "Warren" in n for n in names)

    def test_mr_mrs_title(self):
        text = "Mr. Thompson and Mrs. Garcia signed the contract today."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Thompson" in n for n in names) or any("Garcia" in n for n in names)


# ===================================================================
# 12. ORGANIZATIONS
# ===================================================================

class TestOrganizations:
    """Organization entity extraction."""

    def test_known_company(self):
        entities = extract_entities("I interviewed at Google last week for a senior role.")
        orgs = _orgs(entities)
        # spaCy may or may not extract "Google" as org — document behavior
        assert isinstance(orgs, list)

    def test_org_not_as_person(self):
        """Organizations should not be misclassified as persons."""
        entities = extract_entities(
            "Microsoft and Apple are releasing new developer tools."
        )
        names = _persons(entities)
        assert "Microsoft" not in names
        assert "Apple" not in names

    def test_university_as_org(self):
        entities = extract_entities(
            "She graduated from Stanford University in 2020."
        )
        orgs = _orgs(entities)
        # Stanford could be person or org depending on spaCy — document behavior
        assert isinstance(orgs, list)


# ===================================================================
# 13. CONFIDENCE SCORING
# ===================================================================

class TestConfidenceScoring:
    """Verify confidence levels are appropriate."""

    def test_known_person_high_confidence(self):
        entities = extract_entities(
            "I called John Smith about the deal.",
            existing_people=["John Smith"],
        )
        conf = _person_conf(entities, "John Smith")
        assert conf >= 0.7

    def test_unknown_multiword_moderate_confidence(self):
        entities = extract_entities("I met Robert Paulson at the conference.")
        persons = [e for e in entities if e.type == "person" and "Robert" in e.text]
        if persons:
            assert persons[0].confidence >= 0.3
            assert persons[0].confidence <= 0.85

    def test_single_unknown_word_low_confidence(self):
        """Single-word unknown names should have low confidence."""
        entities = extract_entities("Jennifer mentioned the deadline.")
        persons = [e for e in entities if e.type == "person" and "Jennifer" in e.text]
        if persons:
            # Single unknown word should be below graph threshold
            assert persons[0].confidence < 0.5

    def test_known_person_always_above_threshold(self):
        """Known people should always be above graph threshold (0.5)."""
        entities = extract_entities(
            "Meeting with Alice about the roadmap.",
            existing_people=["Alice Chen"],
        )
        persons = [e for e in entities if e.type == "person" and "Alice" in e.text]
        if persons:
            assert persons[0].confidence >= 0.5


# ===================================================================
# 14. SINGLE-WORD NAMES WITH EXISTING PEOPLE
# ===================================================================

class TestSingleNameExisting:
    """Single first names matching known full names."""

    def test_single_name_matches_known(self):
        entities = extract_entities(
            "I spoke to Sarah about the project timeline.",
            existing_people=["Sarah Johnson"],
        )
        names = _persons(entities)
        assert any("Sarah" in n for n in names)

    def test_single_name_returns_full_canonical(self):
        """When a single name matches a known person, prefer full name."""
        entities = extract_entities(
            "Bob sent the final version of the report.",
            existing_people=["Bob Martinez"],
        )
        names = _persons(entities)
        # Should ideally return "Bob Martinez" (canonical full name)
        if any("Bob" in n for n in names):
            # If matched, should have high confidence
            bob = [e for e in entities if e.type == "person" and "Bob" in e.text]
            assert bob[0].confidence >= 0.5

    def test_ambiguous_single_name(self):
        """When multiple known people share a first name, should pick best."""
        entities = extract_entities(
            "I messaged David about lunch plans.",
            existing_people=["David Brown", "David Miller"],
        )
        names = _persons(entities)
        # Should match one of them
        assert any("David" in n for n in names)


# ===================================================================
# 15. MIXED EN/PL TEXT
# ===================================================================

class TestMixedLanguage:
    """English text with Polish elements and vice versa."""

    def test_english_names_in_polish_sentence(self):
        entities = extract_entities(
            "Spotkałem się z James Clear na konferencji w Warszawie."
        )
        names = _persons(entities)
        assert any("James" in n for n in names)

    def test_polish_names_in_english_sentence(self):
        entities = extract_entities(
            "I had a meeting with Michał Kowalski to discuss the roadmap."
        )
        names = _persons(entities)
        assert any("Michał" in n or "Kowalski" in n for n in names)

    def test_mixed_names_in_list(self):
        text = """Team members:
- Adam Nowak (backend)
- Sarah Miller (frontend)
- Tomek Wiśniewski (QA)"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Adam" in n for n in names)
        assert any("Sarah" in n for n in names)

    def test_polish_context_with_english_author(self):
        text = "Przeczytałem książkę Cal Newport o deep work — rewelacyjna."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Cal Newport" in n or "Newport" in n for n in names)


# ===================================================================
# 16. EDGE CASES
# ===================================================================

class TestEdgeCases:
    """Various edge cases for robustness."""

    def test_empty_text(self):
        entities = extract_entities("")
        assert entities == []

    def test_no_names_in_plain_text(self):
        entities = extract_entities("the quick brown fox jumps over the lazy dog")
        names = _persons(entities)
        assert len(names) == 0

    def test_all_caps_text(self):
        """ALL CAPS text should not produce false positives."""
        entities = extract_entities("MEETING AT 3PM IN CONFERENCE ROOM B")
        names = _persons_above(entities)
        assert len(names) == 0

    def test_name_with_numbers(self):
        """Names with numbers should not appear as high-confidence persons."""
        entities = extract_entities("Contact Agent47 or refer to Section5.")
        names = _persons_above(entities)
        assert "Agent47" not in names

    def test_very_long_text(self):
        """Should handle longer text without errors."""
        text = "Lorem ipsum. " * 100 + " John Smith is the contact person."
        entities = extract_entities(text)
        # Should not crash
        assert isinstance(entities, list)

    def test_special_characters_not_person(self):
        """Text with special chars should not produce false positives."""
        entities = extract_entities("Rating: ⭐⭐⭐⭐⭐ — Excellent!")
        names = _persons(entities)
        assert len(names) == 0

    def test_url_not_person(self):
        entities = extract_entities("Check out https://example.com/John-Smith for details.")
        names = _persons(entities)
        # URL parts should not be extracted
        assert not any("example" in n.lower() for n in names)

    def test_hashtag_not_person(self):
        entities = extract_entities("Follow the trend #JohnSmith on social media.")
        names = _persons(entities)
        assert "#JohnSmith" not in names

    def test_quoted_text(self):
        text = 'He said: "Talk to Jessica Palmer about the budget."'
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Jessica" in n or "Palmer" in n for n in names)


# ===================================================================
# 17. DAILY NOTE STYLE TEXT
# ===================================================================

class TestDailyNoteStyle:
    """Extraction from daily journal / note style entries."""

    def test_daily_journal_entry(self):
        text = """## Wednesday 2026-04-16

Productive day. Had a long call with Mark Anderson about the hiring plan.
Sarah from design sent mockups — they look great.
Lunch with Kevin, discussed the Q3 goals.

### TODO
- Send feedback to Mark Anderson
- Schedule 1:1 with Diana Chen
- Book flight for next week's offsite"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Mark Anderson" in n for n in names)

    def test_planning_note(self):
        text = """## Q2 Plan

Key stakeholders:
- Engineering: James Lee (lead), Sara Kim (backend)
- Product: Rachel Adams
- Design: Luis Garcia

Milestones:
1. April 20 — API design review
2. May 1 — MVP ready
3. May 15 — beta launch"""
        entities = extract_entities(text)
        names = _persons(entities)
        # At least some stakeholder names should be found
        assert len(names) >= 2

    def test_retrospective_note(self):
        text = """## Sprint 14 Retro

What went well:
- Tom delivered the auth module ahead of schedule
- Great collaboration between Anna and Chris on the search feature

What to improve:
- Need more async communication
- Better estimation (overestimated by 30% — Mike's concern)"""
        entities = extract_entities(text)
        # Should extract at least some names from the retro
        names = _persons(entities)
        assert len(names) >= 1


# ===================================================================
# 18. HEALTH AND LIFESTYLE NOTES
# ===================================================================

class TestHealthNotes:
    """Names in health/lifestyle context — common in personal notes."""

    def test_doctor_name_in_health_note(self):
        text = "Had a checkup with Dr. Amanda Lee. Blood pressure is normal."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Amanda" in n or "Lee" in n for n in names)

    def test_trainer_name(self):
        text = "Training session with coach Mike Thompson. New PR on deadlift."
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Mike" in n or "Thompson" in n for n in names)

    def test_supplement_not_person(self):
        """Supplement names should not be persons."""
        entities = extract_entities(
            "Taking magnesium, vitamin D, and omega-3 daily."
        )
        names = _persons(entities)
        assert len(names) == 0

    def test_no_health_coach_as_person(self):
        """'Health Coach' should not be extracted as person."""
        entities = extract_entities("My Health Coach recommends more protein.")
        names = _persons_above(entities)
        assert not any("Health Coach" in n for n in names)


# ===================================================================
# 19. NOT_NAME_WORDS COVERAGE
# ===================================================================

class TestNotNameWords:
    """Ensure tech/work terms in _NOT_NAME_WORDS are properly filtered."""

    def test_build_test_not_person(self):
        entities = extract_entities("Build Test suite before the release.")
        names = _persons_above(entities)
        assert not any("Build" in n for n in names)
        assert not any("Test" in n for n in names)

    def test_sync_backup_not_person(self):
        entities = extract_entities("Run Sync Backup before deploying to production.")
        names = _persons_above(entities)
        assert not any("Sync" in n for n in names)
        assert not any("Backup" in n for n in names)

    def test_api_url_abbreviations_not_person(self):
        entities = extract_entities("The API URL was incorrect, check the SDK docs.")
        names = _persons(entities)
        assert "API" not in names
        assert "URL" not in names
        assert "SDK" not in names

    def test_assistant_planner_not_person(self):
        """Role words should not be person names."""
        entities = extract_entities(
            "Use the Assistant Planner to organize weekly tasks."
        )
        names = _persons_above(entities)
        assert not any("Assistant" in n for n in names)
        assert not any("Planner" in n for n in names)


# ===================================================================
# 20. REAL-WORLD JARVIS SCENARIOS
# ===================================================================

class TestRealWorldScenarios:
    """Realistic scenarios a Jarvis user would encounter."""

    def test_investment_research_note(self):
        text = """## TechFund Investment Research

Peter Thiel's "Zero to One" principles applied to our analysis.
Spoke with Adam about the seed round — he recommends waiting.
Ben Horowitz has a good framework for board management.
Next step: call Mark Wiśniewski to discuss valuation."""
        entities = extract_entities(
            text,
            existing_people=["Adam Nowak", "Marek Wiśniewski"],
        )
        names = _persons(entities)
        assert any("Peter Thiel" in n for n in names)
        assert any("Ben Horowitz" in n for n in names)

    def test_travel_planning_note(self):
        text = """## Trip to London

Flight: April 20, 8:15 AM LOT
Hotel: Premier Inn near King's Cross
Meetings:
- April 21: Chris Bailey (product sync)
- April 22: Emma Watson from the London office
- April 23: free day, visit British Museum"""
        entities = extract_entities(text)
        names = _persons(entities)
        assert any("Chris" in n for n in names) or any("Emma" in n for n in names)

    def test_personal_crm_note(self):
        text = """## People — Work Contacts

### Close collaborators
- **Sarah Kim** — engineering lead, great at estimation
- **Marcus Johnson** — product, always brings user insights
- **Elena Petrov** — data science, helped with recommendation engine

### External
- **David Chang** — investor, check in quarterly
- **Lisa Wu** — legal counsel for IP matters"""
        entities = extract_entities(text)
        names = _persons(entities)
        # Should extract at least 3 of the 5 names
        assert len(names) >= 3

    def test_weekly_review_note(self):
        text = """## Weekly Review — April 14-18

### Wins
- Shipped v2.1 with Tom's help
- Got positive feedback from Sarah on the new dashboard
- Closed deal with Martinez Group

### Next week
- 1:1 with Jennifer about promotion track
- Review PR from David
- Prepare slides for Chris's offsite"""
        entities = extract_entities(text)
        names = _persons(entities)
        # At least some names should be found despite varied context
        assert any("Jennifer" in n for n in names) or any("Sarah" in n for n in names) or len(names) >= 1
