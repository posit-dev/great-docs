"""
Tests for custom page source discovery
"""

from pathlib import Path

from great_docs._content import custom_pages
from great_docs._layout import Layout
from tests.support import write_config


def test_custom_page_sources_skip_section_directory(tmp_path: Path):
    config = write_config(tmp_path, "sections:\n  - title: Pages\n    dir: custom\n")
    (tmp_path / "custom").mkdir()

    assert custom_pages.find_sources(config, Layout.make(tmp_path), report=print) == []


def test_custom_page_sources_skip_a_missing_default_directory_silently(tmp_path: Path):
    config = write_config(tmp_path, "display_name: Demo\n")
    warnings: list[str] = []

    assert custom_pages.find_sources(config, Layout.make(tmp_path), report=warnings.append) == []
    assert warnings == []


def test_custom_page_sources_warn_about_a_missing_configured_directory(tmp_path: Path):
    config = write_config(tmp_path, "custom_pages: custom\n")
    warnings: list[str] = []

    assert custom_pages.find_sources(config, Layout.make(tmp_path), report=warnings.append) == []
    assert warnings == ["Custom pages directory 'custom' not found, skipping"]
