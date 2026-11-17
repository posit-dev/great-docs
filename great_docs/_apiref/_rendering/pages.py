"""Page front matter, which carries the page title"""

from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs._apiref._rendering.base import BaseRenderer

if TYPE_CHECKING:
    from great_docs.pandoc.blocks import BlockContent


class PageRendererMixin(BaseRenderer):
    """Page metadata and front-matter title presentation"""

    def render_metadata(self) -> BlockContent:
        """
        Render the metadata (front-matter) of the page

        The title is rendered in the front-matter.
        """

    def render_title(self):
        return self.render_metadata()
