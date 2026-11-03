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
