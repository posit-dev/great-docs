from __future__ import annotations

from typing import TYPE_CHECKING, cast

from great_docs._qrenderer._render.mixin_page import RenderPageMixin

from ..pandoc.blocks import (
    Blocks,
    Div,
    Meta,
)
from ..pandoc.components import Attr
from .base import RenderBase

if TYPE_CHECKING:
    from ..layout import Layout
    from ..pandoc.blocks import BlockContent


class __RenderReferencePage(RenderPageMixin, RenderBase):
    """
    Render the API Reference Page
    """

    def __post_init__(self):
        self.layout = cast("Layout", self.layout_obj)
        """The layout of the reference page"""

        self.sections = self.layout.sections
        """Top level sections of the quarto config"""

        self.package = self.layout.package
        """The package being documented """

        self.options = self.layout.options

    def render_description(self) -> BlockContent:
        """
        Render the description of the reference page
        """
        return (
            Div(self.layout.description, Attr(classes=["doc-description"]))
            if self.layout.description
            else None
        )

    def render_metadata(self) -> BlockContent:
        return Meta(
            {
                "title": self.layout.title,
                "body-classes": "doc-reference",
                "page-navigation": False,
            }
        )

    def render_body(self) -> BlockContent:
        """
        Render the body of the reference page

        The body is a consists of sections/groups as they are listed in the configuation
        file.

        See Also
        --------
        great_docs.renderer.RenderSection - Rendering of the sections

        Markup and Styling
        ------------------

        | HTML Elements      | CSS Selector       |
        |:-------------------|:-------------------|
        | `<section>`{.html} | `.doc-index`{.css} |
        """
        from . import get_render_type

        render_objs = [get_render_type(s)(s, self.level) for s in self.sections]
        return Blocks(render_objs)


class RenderReferencePage(__RenderReferencePage):
    """
    Extend rendering of the API Reference page
    """
