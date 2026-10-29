"""
Registration of the Markdown companion filter
"""

from pathlib import Path

from great_docs._website import markdown_pages
from great_docs.config import Config
from tests.support import write_config


def test_adds_the_filter_after_existing_filters(tmp_path):
    quarto: dict = {"filters": ["interlinks"]}
    markdown_pages.register(quarto, write_config(tmp_path))
    assert quarto["filters"] == ["interlinks", "markdown-pages"]


def test_adds_nothing_when_disabled(tmp_path):
    quarto: dict = {}
    markdown_pages.register(quarto, write_config(tmp_path, "markdown_pages: false\n"))
    assert quarto == {}


def test_never_adds_the_filter_twice(tmp_path):
    quarto: dict = {"filters": ["markdown-pages"]}
    markdown_pages.register(quarto, write_config(tmp_path))
    assert quarto["filters"] == ["markdown-pages"]
