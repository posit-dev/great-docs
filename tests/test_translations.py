"""Tests for the i18n translation module."""

import json

import pytest

from great_docs._translations import (
    DEFAULT_LANGUAGE,
    RTL_LANGUAGES,
    SUPPORTED_LANGUAGES,
    UI_TRANSLATIONS,
    get_locale_for_dates,
    get_translation,
    get_translations_bundle,
    is_rtl,
)


class TestGetTranslation:
    """Tests for get_translation()."""

    def test_default_english(self):
        assert get_translation("back_to_top") == "Back to top"

    def test_explicit_english(self):
        assert get_translation("back_to_top", "en") == "Back to top"

    def test_french(self):
        assert get_translation("back_to_top", "fr") == "Retour en haut"

    def test_german(self):
        assert get_translation("copied", "de") == "Kopiert!"

    def test_japanese(self):
        assert get_translation("back_to_top", "ja") == "トップに戻る"

    def test_chinese_simplified(self):
        assert get_translation("back_to_top", "zh-Hans") == "回到顶部"

    def test_arabic(self):
        assert get_translation("back_to_top", "ar") == "العودة للأعلى"

    def test_unknown_key_returns_key(self):
        assert get_translation("nonexistent_key") == "nonexistent_key"

    def test_unknown_language_falls_back_to_english(self):
        assert get_translation("back_to_top", "xx") == "Back to top"

    def test_placeholder_preserved(self):
        result = get_translation("refreshed_time_ago", "en")
        assert "{time}" in result

    def test_plural_pipe_format(self):
        result = get_translation("years_ago", "en")
        assert "|" in result
        parts = result.split("|")
        assert "{n}" in parts[0]
        assert "{n}" in parts[1]


class TestGetTranslationsBundle:
    """Tests for get_translations_bundle()."""

    def test_bundle_returns_dict(self):
        bundle = get_translations_bundle("en")
        assert isinstance(bundle, dict)

    def test_bundle_contains_all_keys(self):
        bundle = get_translations_bundle("en")
        for key in UI_TRANSLATIONS:
            assert key in bundle

    def test_bundle_french_values(self):
        bundle = get_translations_bundle("fr")
        assert bundle["back_to_top"] == "Retour en haut"
        assert bundle["copied"] == "Copié !"

    def test_bundle_unknown_language_falls_back(self):
        bundle = get_translations_bundle("xx")
        assert bundle["back_to_top"] == "Back to top"

    def test_bundle_is_json_serializable(self):
        bundle = get_translations_bundle("ja")
        serialized = json.dumps(bundle, ensure_ascii=False)
        assert "トップに戻る" in serialized

    def test_bundle_default_is_english(self):
        bundle_default = get_translations_bundle()
        bundle_en = get_translations_bundle("en")
        assert bundle_default == bundle_en


class TestIsRtl:
    """Tests for is_rtl()."""

    def test_arabic_is_rtl(self):
        assert is_rtl("ar") is True

    def test_hebrew_is_rtl(self):
        assert is_rtl("he") is True

    def test_english_is_not_rtl(self):
        assert is_rtl("en") is False

    def test_french_is_not_rtl(self):
        assert is_rtl("fr") is False

    def test_japanese_is_not_rtl(self):
        assert is_rtl("ja") is False


class TestGetLocaleForDates:
    """Tests for get_locale_for_dates()."""

    def test_english(self):
        assert get_locale_for_dates("en") == "en"

    def test_chinese_simplified_maps_to_cn(self):
        assert get_locale_for_dates("zh-Hans") == "zh-CN"

    def test_chinese_traditional_maps_to_tw(self):
        assert get_locale_for_dates("zh-Hant") == "zh-TW"

    def test_french_passthrough(self):
        assert get_locale_for_dates("fr") == "fr"


class TestTranslationCompleteness:
    """Verify that all translations are complete across supported languages."""

    def test_all_supported_languages_listed(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert len(SUPPORTED_LANGUAGES) >= 14

    def test_default_language_is_english(self):
        assert DEFAULT_LANGUAGE == "en"

    def test_all_keys_have_english(self):
        for key, entry in UI_TRANSLATIONS.items():
            assert "en" in entry, f"Key '{key}' missing English translation"

    def test_all_supported_languages_have_translations(self):
        """Every supported language should have a translation for every key."""
        missing = []
        for key, entry in UI_TRANSLATIONS.items():
            for lang in SUPPORTED_LANGUAGES:
                if lang not in entry:
                    missing.append(f"{key}[{lang}]")
        assert missing == [], f"Missing translations: {', '.join(missing[:20])}"

    def test_rtl_languages_are_subset_of_supported(self):
        # ar and he are deactivated (RTL layout WIP) but still in RTL_LANGUAGES
        deactivated_rtl = {"ar", "he"}
        for lang in RTL_LANGUAGES:
            if lang in ("fa", "ur") or lang in deactivated_rtl:
                continue
            assert lang in SUPPORTED_LANGUAGES, f"RTL language '{lang}' not in SUPPORTED_LANGUAGES"

    def test_no_empty_translations(self):
        """No translation value should be an empty string."""
        for key, entry in UI_TRANSLATIONS.items():
            for lang, value in entry.items():
                assert value.strip(), f"Empty translation: {key}[{lang}]"

    def test_placeholder_consistency(self):
        """Placeholders in English should appear in all translations."""
        import re

        for key, entry in UI_TRANSLATIONS.items():
            en_text = entry.get("en", "")
            en_placeholders = set(re.findall(r"\{(\w+)\}", en_text))
            if not en_placeholders:
                continue
            for lang, text in entry.items():
                if lang == "en":
                    continue
                lang_placeholders = set(re.findall(r"\{(\w+)\}", text))
                assert en_placeholders == lang_placeholders, (
                    f"Placeholder mismatch in {key}[{lang}]: "
                    f"expected {en_placeholders}, got {lang_placeholders}"
                )

    def test_all_keys_have_all_languages(self):
        """Every key in UI_TRANSLATIONS must have an entry for every SUPPORTED_LANGUAGES code."""
        for key, entry in UI_TRANSLATIONS.items():
            missing = [lang for lang in SUPPORTED_LANGUAGES if lang not in entry]
            assert not missing, f"Translation key '{key}' is missing languages: {missing}"
