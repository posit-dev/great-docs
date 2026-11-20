"""Tests for great_docs._apiref.write."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._apiref.write import (
    _insert_contents,
    merge_frontmatter,
)


class TestMergeFrontmatter:
    def test_unclosed_frontmatter_raises(self):
        """Raises ValueError when frontmatter is never closed."""
        content = "---\ntitle: Hello\nNo closing delimiter here.\n"
        with pytest.raises(ValueError, match="never closed"):
            merge_frontmatter(content, {"key": "val"})


class TestInsertContents:
    def test_sentinel_in_dict_nested_in_list(self):
        """Finds sentinel in a dict nested inside a list."""
        structure = [
            "item1",
            {"section": "A", "contents": ["{{ contents }}"]},
        ]
        result = _insert_contents(structure, ["new1", "new2"])
        assert result is True
        assert structure[1]["contents"] == ["new1", "new2"]

    def test_sentinel_in_list_nested_in_list(self):
        """Finds sentinel in a list nested inside a list."""
        structure = [
            "item1",
            ["nested", "{{ contents }}"],
        ]
        result = _insert_contents(structure, ["replaced"])
        assert result is True
        assert structure[1] == ["nested", "replaced"]

    def test_dict_value_dict_no_sentinel(self):
        """Dict value that is a dict without the sentinel returns False."""
        structure = {"outer": {"inner": "value"}}
        assert _insert_contents(structure, ["x"]) is False

    def test_dict_value_list_no_sentinel(self):
        """Dict value that is a list without the sentinel returns False."""
        structure = {"outer": ["value"]}
        assert _insert_contents(structure, ["x"]) is False

    def test_list_item_dict_no_sentinel(self):
        """List item that is a dict without the sentinel returns False."""
        structure = [{"key": "value"}]
        assert _insert_contents(structure, ["x"]) is False

    def test_list_item_list_no_sentinel(self):
        """List item that is a list without the sentinel returns False."""
        structure = [["value"]]
        assert _insert_contents(structure, ["x"]) is False


class TestPageSidebarText:
    def test_summary_not_none_returns_summary_name(self):
        """When page.summary is set, returns its name."""
        from great_docs._apiref.write import _page_sidebar_text

        page = MagicMock()
        page.summary = MagicMock()
        page.summary.name = "MyWidget"

        result = _page_sidebar_text(page)
        assert result == "MyWidget"


class TestGenerateSidebar:
    def test_second_titled_section_appends_previous(self):
        """A second titled section appends the previous current_entry."""
        from great_docs._apiref.content import Page, Section
        from great_docs._apiref.write import _generate_sidebar

        page1 = MagicMock(spec=Page)
        page1.summary = None
        page1.contents = [MagicMock(name="func_a", kind="function")]
        page1.contents[0].name = "func_a"
        page1.contents[0].kind = "function"
        page1.path = "func_a"

        page2 = MagicMock(spec=Page)
        page2.summary = None
        page2.contents = [MagicMock(name="ClassB", kind="class")]
        page2.contents[0].name = "ClassB"
        page2.contents[0].kind = "class"
        page2.path = "ClassB"

        sec1 = MagicMock(spec=Section)
        sec1.title = "Functions"
        sec1.subtitle = None
        sec1.contents = [page1]

        sec2 = MagicMock(spec=Section)
        sec2.title = "Classes"
        sec2.subtitle = None
        sec2.contents = [page2]

        result = _generate_sidebar(
            [sec1, sec2], dir="reference", out_page_suffix=".qmd", sidebar=None
        )

        sidebar_contents = result["website"]["sidebar"][0]["contents"]
        sections = [c for c in sidebar_contents if isinstance(c, dict) and "section" in c]
        assert len(sections) == 2
        assert sections[0]["section"] == "Functions"
        assert sections[1]["section"] == "Classes"

    def test_non_page_entry_is_skipped(self):
        """Section contents that are not Page instances are skipped."""
        from great_docs._apiref.content import Page, Section
        from great_docs._apiref.write import _generate_sidebar

        page = MagicMock(spec=Page)
        page.summary = None
        page.contents = [MagicMock(name="func_a", kind="function")]
        page.contents[0].name = "func_a"
        page.contents[0].kind = "function"
        page.path = "func_a"

        sec = MagicMock(spec=Section)
        sec.title = "Functions"
        sec.subtitle = None
        sec.contents = [MagicMock(), page]  # a non-Page entry followed by a Page

        result = _generate_sidebar([sec], dir="reference", out_page_suffix=".qmd", sidebar=None)

        sidebar_contents = result["website"]["sidebar"][0]["contents"]
        section = next(c for c in sidebar_contents if isinstance(c, dict) and "section" in c)
        assert len(section["contents"]) == 1
        assert section["contents"][0]["href"] == "reference/func_a.qmd"


class TestCollectTypingInformation:
    def test_collects_each_module(self, tmp_path: Path):
        """Collect a publishable typing source for each requested module"""
        from great_docs._apiref.write import RenderedPage, collect_typing_information

        mock_api_ref = MagicMock()

        with patch("great_docs._apiref.typing_information.TypeInformation") as MockTI:
            mock_instance = MagicMock()
            mock_instance.collect.side_effect = [
                RenderedPage(tmp_path / "pkg.types.qmd", "Type variables"),
                RenderedPage(tmp_path / "pkg.protocols.qmd", "Protocols"),
            ]
            MockTI.return_value = mock_instance

            collected = collect_typing_information(["pkg.types", "pkg.protocols"], mock_api_ref)

        for rendered in collected:
            rendered.write()
        assert MockTI.call_count == 2
        MockTI.assert_any_call("pkg.types", mock_api_ref)
        MockTI.assert_any_call("pkg.protocols", mock_api_ref)
        assert (tmp_path / "pkg.types.qmd").read_text() == "Type variables"
        assert (tmp_path / "pkg.protocols.qmd").read_text() == "Protocols"
