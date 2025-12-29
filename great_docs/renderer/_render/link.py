from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quartodoc.pandoc.blocks import (
    Blocks,
    Div,
)
from quartodoc.pandoc.components import Attr

from .._format import markdown_escape
from .._pandoc.inlines import InterLink
from .base import RenderBase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quartodoc.layout import Link

    from ..typing import SummaryItem


class __RenderLink(RenderBase):
    """
    Render a Link object (layout.Link)
    """

    def __post_init__(self):
        self.link = cast("Link", self.layout_obj)
        """Link being documented"""

        self.obj = self.link.obj
        """Griffe object"""

    def __str__(self):
        """
        The Doc object rendered to quarto markdown
        """
        return str(
            Div(
                Blocks([self.title, self.description, self.body]),
                Attr(classes=["doc"]),
            )
        )

    def render_summary(self) -> Sequence[SummaryItem]:
        link = InterLink(None, markdown_escape(self.link.name))
        text = self.obj.docstring.value.splitlines()[0] if self.obj.docstring else ""
        return [(str(link), text)]

class RenderLink(__RenderLink):
    """
    Extend Rendering of a layout.Link object
    """
