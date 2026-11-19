"""Tests for great_docs.pandoc.inlines."""

from __future__ import annotations

from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code


class TestInlinesEmpty:
    def test_inlines_empty_returns_empty(self):
        """Inlines with no elements returns ''."""
        from great_docs.pandoc.inlines import Inlines

        assert str(Inlines(elements=None)) == ""
        assert str(Inlines(elements=[])) == ""

    def test_inlines0_empty_returns_empty(self):
        """Inlines0 with no elements returns ''."""
        from great_docs.pandoc.inlines import Inlines0

        assert str(Inlines0(elements=None)) == ""
        assert str(Inlines0(elements=[])) == ""


def test_code_uses_a_delimiter_longer_than_embedded_backticks() -> None:
    assert str(Code("`edge``")) == "``` `edge`` ```"


def test_code_preserves_attributes_with_embedded_backticks() -> None:
    attr = Attr(classes=["gd-no-link"])
    assert str(Code("call('`')", attr)) == "`` call('`') ``{.gd-no-link}"
