"""Tests for great_docs._apiref.api_reference."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestMemberName:
    def test_page_returns_first_content_name(self):
        """Page node returns contents[0].name."""
        from great_docs._apiref.api_reference import _member_name
        from great_docs._apiref.content import Page

        page = MagicMock(spec=Page)
        page.contents = [MagicMock(name="my_func")]
        page.contents[0].name = "my_func"

        assert _member_name(page) == "my_func"


class TestMemberChildren:
    def test_page_returns_first_content_members(self):
        """Page node returns contents[0].members."""
        from great_docs._apiref.api_reference import _member_children
        from great_docs._apiref.content import Page

        inner = MagicMock()
        inner.members = ["child1", "child2"]
        page = MagicMock(spec=Page)
        page.contents = [inner]

        assert _member_children(page) == ["child1", "child2"]
