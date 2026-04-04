from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs._renderer._render.base import RenderBase

if TYPE_CHECKING:
    from ..pandoc.blocks import BlockContent


class __RenderPageMixin(RenderBase):
    def render_metadata(self) -> BlockContent:
        """
        Render the metadata (front-matter) of the page

        The title is rendered in the front-matter.
        """

    def render_title(self):
        return self.render_metadata()


class RenderPageMixin(__RenderPageMixin):
    """
    Extend Rendering of pages
    """
