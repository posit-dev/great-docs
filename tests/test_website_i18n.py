"""
Translation bundle and text direction for non-English sites
"""

import html
import json
from pathlib import Path
from typing import Any

from great_docs._translations import (
    QUARTO_LANGUAGE_KEYS,
    get_translation,
    get_translations_bundle,
)
from great_docs._website import i18n
from great_docs.config import Config
from tests.support import write_config

PAGE = "<html><head><title>T</title></head><body></body></html>"


class TestRegister:
    def test_rtl_language_sets_direction(self, tmp_path):
        quarto_config = {"format": {"html": {}}}
        i18n.register(quarto_config, write_config(tmp_path, "site:\n  lang: ar\n"))
        assert quarto_config["format"]["html"]["dir"] == "rtl"

    def test_ltr_language_leaves_direction_unset(self, tmp_path):
        for lang in ("fr", "en"):
            quarto_config = {"format": {"html": {}}}
            i18n.register(quarto_config, write_config(tmp_path, f"site:\n  lang: {lang}\n"))
            assert "dir" not in quarto_config["format"]["html"]

    def test_user_direction_wins(self, tmp_path):
        quarto_config = {"format": {"html": {"dir": "ltr"}}}
        i18n.register(quarto_config, write_config(tmp_path, "site:\n  lang: ar\n"))
        assert quarto_config["format"]["html"]["dir"] == "ltr"


class TestMetaTag:
    def test_none_for_english(self, tmp_path):
        assert i18n.meta_tag(write_config(tmp_path, "site:\n  lang: en\n")) is None

    def test_content_is_the_escaped_bundle(self, tmp_path):
        tag = i18n.meta_tag(write_config(tmp_path, "site:\n  lang: fr\n"))
        assert tag is not None
        prefix, suffix = '<meta name="gd-i18n" content="', '">'
        assert tag.startswith(prefix) and tag.endswith(suffix)
        content = tag[len(prefix) : -len(suffix)]
        assert json.loads(html.unescape(content)) == get_translations_bundle("fr")


class TestAddToRawPage:
    def test_inserts_once(self, tmp_path):
        config = write_config(tmp_path, "site:\n  lang: fr\n")
        page = i18n.add_to_raw_page(PAGE, config)
        assert page.count('name="gd-i18n"') == 1
        assert i18n.add_to_raw_page(page, config) == page

    def test_english_page_unchanged(self, tmp_path):
        assert i18n.add_to_raw_page(PAGE, write_config(tmp_path, "site:\n  lang: en\n")) == PAGE

    def test_rtl_language_sets_direction(self, tmp_path):
        page = i18n.add_to_raw_page(
            '<html lang="ar"><head></head></html>', write_config(tmp_path, "site:\n  lang: ar\n")
        )
        assert page.startswith('<html lang="ar" dir="rtl">')

    def test_site_direction_wins(self, tmp_path):
        config = write_config(tmp_path, "site:\n  lang: ar\n  dir: ltr\n")
        page = i18n.add_to_raw_page(PAGE, config)
        assert page.startswith('<html dir="ltr">')

    def test_page_direction_is_kept(self, tmp_path):
        page = i18n.add_to_raw_page(
            '<html dir="ltr"><head></head></html>', write_config(tmp_path, "site:\n  lang: ar\n")
        )
        assert page.startswith('<html dir="ltr">')
        assert page.count("dir=") == 1

    def test_ltr_language_leaves_direction_unset(self, tmp_path):
        assert "dir=" not in i18n.add_to_raw_page(
            PAGE, write_config(tmp_path, "site:\n  lang: fr\n")
        )


class TestRegisterTocTitle:
    def test_title_follows_the_language(self, tmp_path: Path):
        quarto_config = {"format": {"html": {"toc-title": "On this page"}}}
        i18n.register_toc_title(quarto_config, write_config(tmp_path, "site:\n  lang: fr\n"))
        assert quarto_config["format"]["html"]["toc-title"] == get_translation("on_this_page", "fr")

    def test_site_title_wins(self, tmp_path: Path):
        quarto_config = {"format": {"html": {"toc-title": "Contents"}}}
        config = write_config(tmp_path, "site:\n  lang: fr\n  toc-title: Contents\n")
        i18n.register_toc_title(quarto_config, config)
        assert quarto_config["format"]["html"]["toc-title"] == "Contents"


class TestRegisterQuartoStrings:
    def test_untranslated_language_keeps_set_strings(self, tmp_path: Path):
        quarto_config = {"language": {"ar": {"search-label": "Mine"}, "fr": {}}}
        i18n.register_quarto_strings(quarto_config, write_config(tmp_path, "site:\n  lang: ar\n"))
        strings = quarto_config["language"]["ar"]
        assert strings["search-label"] == "Mine"
        assert strings.keys() == QUARTO_LANGUAGE_KEYS.keys()
        assert quarto_config["language"]["fr"] == {}

    def test_translated_language_unchanged(self, tmp_path: Path):
        quarto_config: dict[str, Any] = {}
        i18n.register_quarto_strings(quarto_config, write_config(tmp_path, "site:\n  lang: fr\n"))
        assert quarto_config == {}
