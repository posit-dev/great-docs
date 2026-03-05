from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, cast

from great_docs._qrenderer._render.mixin_page import RenderPageMixin
from great_docs._renderer.pandoc.inlines import Link

from ..._renderer.pandoc.blocks import (
    BlockContent,
    Blocks,
    DefinitionItem,
)
from .._format import markdown_escape
from .._pandoc.blocks import Meta
from .base import RenderBase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..._renderer.layout import Page
    from .doc import RenderDoc

# NOTE: While quartodoc has Page.summary attribute, at the moment it is not used
# so self.page.summary is None, always.


class __RenderAPIPage(RenderPageMixin, RenderBase):
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
        render_objs: list[RenderDoc] = [
            get_render_type(c)(
                c,
                self.renderer,
                level,
                page_path=self.path,
            )
            for c in self.page.contents
        ]

        # For a top level object, the title will be created by
        # this api-page as front-matter, rather than a regular header.
        for obj in render_objs:
            if obj.level == 1:
                self.show_title = False

        return render_objs

    def render_metadata(self) -> BlockContent:
        # Derive the title of the page from the first (top-level) object
        obj = self.render_objs[0]
        title = obj._title  # pyright: ignore[reportPrivateUsage]
        return Meta({
            "title": f"{title}",
            "body-classes": "doc-api-page",
        })

    def render_body(self) -> BlockContent:
        """
        Render the body of the documentation page
        """
        return Blocks(self.render_objs)

    def render_summary(self) -> Sequence[DefinitionItem]:
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
