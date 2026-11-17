"""The reference index with explicitly resolved sections"""

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
    from pathlib import Path

    from great_docs.pandoc.blocks import BlockContent

    from .._customisation import Extension
    from ..api_reference import APIReference
    from ..content import Section
    from ._renderers import Renderers


class ReferenceIndexRenderer(PageRendererMixin, BaseRenderer):
    """
    The reference index page, listing resolved sections
    """

    def __init__(
        self,
        api_ref: APIReference,
        sections: list[Section],
        level: int = 1,
        *,
        renderers: Renderers | None = None,
        extension: Extension | None = None,
        output_root: Path | None = None,
        context_page_path: str | None = None,
    ) -> None:
        """Initialise common renderer state from a reference and resolved sections"""
        self.api_ref = api_ref
        """The API reference being documented"""

        self.sections = sections
        """Resolved top-level sections of the quarto config"""

        self.package = api_ref.package
        """The package being documented"""

        self.options = api_ref.options

        super().__init__(
            api_ref,
            level,
            settings=api_ref.settings,
            renderers=renderers or api_ref.renderers,
            extension=extension or api_ref.extension,
            output_root=output_root if output_root is not None else api_ref.output_root,
            context_page_path=context_page_path,
        )

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
        object_renderers = [
            self.renderers.make(
                s,
                self.level,
                settings=self.settings,
                extension=self.extension,
                output_root=self.output_root,
                context_page_path=self.context_page_path,
            )
            for s in self.sections
        ]
        return Blocks(object_renderers)
