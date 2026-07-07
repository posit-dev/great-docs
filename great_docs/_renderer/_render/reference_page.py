from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs._renderer._render.mixin_page import RenderPageMixin

from ..pandoc.blocks import (
    Blocks,
    Div,
    Meta,
)
from ..pandoc.components import Attr
from .base import RenderBase

if TYPE_CHECKING:
    from ..api_reference import APIReference
    from ..content import Section
    from ..pandoc.blocks import BlockContent


class __RenderReferencePage(RenderPageMixin, RenderBase):
    """
    Render the API Reference Page
    """

    def __init__(
        self,
        api_ref: APIReference,
        sections: list[Section],
        level: int = 1,
    ) -> None:
        self.api_ref = api_ref
        """The API reference being documented"""

        self.sections = sections
        """Resolved top-level sections of the quarto config"""

        self.package = api_ref.package
        """The package being documented"""

        self.options = api_ref.options

        self.level = level
        self.show_title = True
        self.show_description = True
        self.show_body = True

        self.__post_init__()

    def render_description(self) -> BlockContent:
        """
        Render the description of the reference page
        """
        return (
            Div(self.api_ref.desc, Attr(classes=["doc-description"])) if self.api_ref.desc else None
        )

    def render_metadata(self) -> BlockContent:
        return Meta(
            {
                "title": self.api_ref.title,
                "body-classes": "doc-reference",
                "page-navigation": False,
                "html-table-processing": "none",
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
