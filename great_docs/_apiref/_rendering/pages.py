"""Page front matter, which carries the page title"""

from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs._apiref._rendering.base import BaseRenderer

if TYPE_CHECKING:
    from great_docs.pandoc.blocks import BlockContent


class PageRendererMixin(BaseRenderer):
    """
    A page renderer whose title is the page's front matter

    Override `render_metadata` to change the front matter. The page body does not
    depend on it.
    """

    def render_metadata(self) -> BlockContent:
        """
        Render page front matter, or return `None` to omit it

        Returns
        -------
        :
            The front matter, or `None` to omit it.
        """

    def render_title(self):
        """
        Render the page title as the page's front matter

        Returns
        -------
        :
            The front matter, or `None` to omit it.
        """
        return self.render_metadata()
