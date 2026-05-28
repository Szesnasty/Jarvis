"""Step 30a — language detection with stop-words + sticky language."""
import pytest

from services.claude import _detect_language, _language_reminder


class TestDetectLanguage:
    def test_diacritic_polish(self):
        assert _detect_language("Cześć, jak się masz?") == "Polish"

    def test_diacriticless_polish_stopwords(self):
        # "co tam" used to default to English — Step 30a fixes that.
        assert _detect_language("co tam") == "Polish"
        assert _detect_language("powiedz mi wiecej") == "Polish"
        assert _detect_language("kim jest adam") == "Polish"

    def test_clear_english(self):
        assert _detect_language("can you help me with the report") == "English"

    def test_german_stopwords(self):
        assert _detect_language("ich habe nicht viel zeit") == "German"

    def test_spanish_stopwords(self):
        assert _detect_language("que pero como estas") == "Spanish"

    def test_french_diacritic(self):
        assert _detect_language("bonjour, ça va?") == "French"

    def test_cyrillic(self):
        assert _detect_language("Привет, как дела?").startswith("Russian")

    def test_short_ambiguous_returns_none(self):
        # 1–2 tokens with no stop-words / diacritics → ambiguous.
        assert _detect_language("ok") is None
        assert _detect_language("hmm thanks") is None

    def test_empty(self):
        assert _detect_language("") is None
        assert _detect_language("   ") is None


class TestLanguageReminder:
    def test_polish_diacriticless_reminds_polish(self):
        msg = _language_reminder("co tam")
        assert "Polish" in msg

    def test_sticky_inherits_from_recent(self):
        # "a teraz?" alone is ambiguous — should inherit Polish from prior.
        msg = _language_reminder(
            "a teraz?",
            recent=["Cześć, jak się masz?", "Powiedz mi o Adamie"],
        )
        assert "Polish" in msg

    def test_ambiguous_no_recent_falls_back_english(self):
        msg = _language_reminder("ok")
        assert "English" in msg

    def test_empty_message(self):
        msg = _language_reminder("")
        assert "FINAL REMINDER" in msg

    def test_clear_english_not_overridden(self):
        msg = _language_reminder(
            "what is the deadline",
            recent=["Cześć, jak się masz?"],
        )
        # Clear English wins over sticky Polish.
        assert "English" in msg
