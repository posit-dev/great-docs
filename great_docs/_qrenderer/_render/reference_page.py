from __future__ import annotations

from typing import TYPE_CHECKING, cast

from great_docs._renderer.pandoc.blocks import (
    Blocks,
    Header,
)
from great_docs._renderer.pandoc.components import Attr

from .base import RenderBase

if TYPE_CHECKING:
    from great_docs._renderer.layout import Layout
    from great_docs._renderer.pandoc.blocks import BlockContent


class __RenderReferencePage(RenderBase):
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

    def render_title(self) -> BlockContent:
        """
        The title of the reference page

        Notes
        -----
        This method is currently ignored and overriding it will not give a
        useful result.
        """
        return Header(1, self.layout.title, Attr(classes=["doc", "doc-index"])),

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

        render_objs = [get_render_type(s)(s, self.renderer, self.level) for s in self.sections]
        return Blocks(render_objs)


class RenderReferencePage(__RenderReferencePage):
    """
    Extend rendering of the API Reference page
    """
