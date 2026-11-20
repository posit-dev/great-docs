"""
The reference index page, with its front matter and sections

The index shows the supplied sections in their authored order, with summary rows
rather than object bodies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs._apiref._rendering.pages import PageRendererMixin
from great_docs._content.metadata import metadata_value
from great_docs.pandoc.blocks import (
    Blocks,
    Div,
    Meta,
)
from great_docs.pandoc.components import Attr

from .base import BaseRenderer

if TYPE_CHECKING:
    from great_docs.pandoc.blocks import BlockContent

    from ..api_reference import APIReference
    from ..content import Section
    from ._renderers import Renderers


class ReferenceIndexRenderer(PageRendererMixin, BaseRenderer):
    """
    The reference index page, listing resolved sections

    The page title is in the front matter. Each section contributes a heading, a
    description and summary rows.
    """

    def __init__(
        self,
        api_ref: APIReference,
        sections: list[Section],
        level: int = 1,
        *,
        renderers: Renderers | None = None,
    ) -> None:
        """
        Set up the index for a reference and its resolved sections

        Parameters
        ----------
        api_ref
            The reference that supplies the title, description, extension and default
            renderer choices.
        sections
            Resolved top-level sections in the order to display.
        level
            Base heading depth for section titles and subtitles.
        renderers
            The renderer choices to use, or `None` for the reference's own.
        """
        self.api_ref = api_ref
        """The API reference being documented"""

        self.sections = sections
        """Resolved top-level sections in authored reference order"""

        self.package = api_ref.package
        """The package being documented"""

        self.options = api_ref.options

        super().__init__(
            api_ref, level, renderers=renderers or api_ref.renderers, extension=api_ref.extension
        )

    def render_description(self) -> BlockContent:
        """
        Render the description of the reference page

        Returns
        -------
        :
            The description in a `doc-description` division, or `None` when the reference
            has no description.
        """
        return (
            Div(self.api_ref.desc, Attr(classes=["doc-description"])) if self.api_ref.desc else None
        )

    def render_metadata(self) -> BlockContent:
        """
        Render the reference title, description metadata and index navigation settings

        Returns
        -------
        :
            The front matter of the reference index page.
        """
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
        Render the sections in their authored order

        Each section renders its heading, description and summary rows.

        Returns
        -------
        :
            The rendered sections.
        """
        return Blocks([self.make_renderer(s, self.level) for s in self.sections])
