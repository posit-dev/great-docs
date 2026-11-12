from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs._apiref._render.mixin_page import RenderPageMixin
from great_docs._content.metadata import metadata_value
from great_docs.pandoc.blocks import (
    Blocks,
    Div,
    Meta,
)
from great_docs.pandoc.components import Attr

from .base import RenderBase

if TYPE_CHECKING:
    from great_docs.pandoc.blocks import BlockContent

    from ..api_reference import APIReference
    from ..content import Section


class __RenderReferencePage(RenderPageMixin, RenderBase):
    """
    Render the API Reference page
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

        self.settings = api_ref.settings

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
        metadata: dict[str, object] = {
            "title": self.api_ref.title,
            "body-classes": "doc-reference doc-py-reference",
            "page-navigation": False,
            "html-table-processing": "none",
            "shift-heading-level-by": 0,
            # Disabling breadcrumbs lets Quarto use the page title in the narrow-screen
            # navigation bar; CSS adds the prefix for the reference type.
            "bread-crumbs": False,
        }
        # Subtitle headings render at `h3`; preserve any deeper site setting.
        if self.api_ref.site_toc_depth < 3:
            metadata["toc-depth"] = 3
        if description := metadata_value(self.api_ref.desc):
            metadata["description-meta"] = description
        return Meta(metadata)

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

        render_objs = [
            get_render_type(s)(s, self.level, settings=self.settings) for s in self.sections
        ]
        return Blocks(render_objs)


class RenderReferencePage(__RenderReferencePage):
    """
    Extension point for the rendering of the API Reference page
    """
