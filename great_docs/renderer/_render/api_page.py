from __future__ import annotations

from copy import copy
from functools import cached_property
from typing import TYPE_CHECKING, cast

from quartodoc.pandoc.blocks import (
    BlockContent,
    Blocks,
    Div,
    Header,
)
from quartodoc.pandoc.components import Attr
from quartodoc.pandoc.inlines import Link

from .._format import markdown_escape
from .._pandoc.blocks import RawHTMLBlockTag
from .base import RenderBase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quartodoc.layout import Page

    from ..typing import RenderObjType, SummaryItem
    from .doc import RenderDoc

# NOTE: While quartodoc has Page.summary attribute, at the moment it is not used
# so self.page.summary is None, always.


class __RenderAPIPage(RenderBase):
    """
    Render an API Page object (layout.Page)
    """

    def __post_init__(self):
        self.page = cast("Page", self.layout_obj)
        """Page in the documentation"""

        self.path = f"{self.page.path}.qmd"
        """All objects on this page are rendered at this path"""

    @property
    def _has_one_object(self):
        return len(self.page.contents) == 1

    @cached_property
    def render_objs(self):
        """
        Render objects on the API page
        """
        from . import get_render_type

        level = self.level if self._has_one_object else self.level + 1
        render_objs: list[RenderObjType] = [
            get_render_type(c)(  # pyright: ignore[reportCallIssue,reportArgumentType]
                c,
                self.renderer,
                level,
                page_path=self.path,
            )
            for c in self.page.contents
        ]
        return render_objs

    def render_title(self) -> BlockContent:
        """
        Render the title/header of a docstring, including any anchors
        """
        title = ""
        # If a page documents a single object, lift-up the title of
        # that object to be the quarto-title of the page.
        if self._has_one_object:
            body = cast("Blocks", self.body)
            if body.elements:
                rendered_obj = cast("RenderDoc", body.elements[0])
                rendered_obj.show_title = False
                title = cast("Header", copy(rendered_obj.title))
        elif self.page.summary:
            title = Header(self.level, markdown_escape(self.page.summary.name))

        header = RawHTMLBlockTag(
            "header",
            Div(title, Attr(classes=["quarto-title"])),
            Attr("title-block-header", classes=["quarto-title-block", "default"]),
        )
        return header

    def render_body(self) -> BlockContent:
        """
        Render the body of the documentation page
        """
        return Blocks(self.render_objs)

    def render_summary(self) -> Sequence[SummaryItem]:
        page = self.page
        if page.summary is not None:
            link = Link(markdown_escape(page.summary.name), self.path)
            items = [(str(link), page.summary.desc)]
        elif len(page.contents) > 1 and not page.flatten:
            msg = (
                f"Cannot summarize page {page.path}. "
                "Either set its `summary` attribute with name and"
                "description details, or set `flatten` to True."
            )
            raise ValueError(msg)
        else:
            items = [row for d in self.render_objs for row in d.render_summary()]
        return items


class RenderAPIPage(__RenderAPIPage):
    """
    Extend Rendering of an API Page
    """
