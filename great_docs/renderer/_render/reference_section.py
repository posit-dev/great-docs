from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from quartodoc.pandoc.blocks import (
    BlockContent,
    DefinitionList,
    Div,
    Header,
)
from quartodoc.pandoc.components import Attr
from tabulate import tabulate

from .base import RenderBase

if TYPE_CHECKING:
    from typing import Literal

    from quartodoc.layout import Section

    from ..typing import RenderObjType


@dataclass
class __RenderReferenceSection(RenderBase):
    """
    Render a section object (layout.Section)

    This is a section of the index/reference page
    """

    layout_format: Literal["list", "table"] = "list"

    def __post_init__(self):
        self.section = cast("Section", self.layout_obj)
        """Section of the reference page"""

    def render_title(self) -> BlockContent:
        """
        Render title or subtitle of section

        Markup and Styling
        ------------------

        | Type     | HTML Elements | CSS Selector                       |
        |:---------|:--------------|:-----------------------------------|
        | title    | `<h2>`{.html} | `.doc-index .doc-group > h2`{.css} |
        | subtitle | `<h3>`{.html} | `.doc-index .doc-group > h3`{.css} |
        """
        if self.section.title:
            level, title = self.level + 1, self.section.title
        elif self.section.subtitle:
            level, title = self.level + 2, self.section.subtitle
        else:
            return None
        return Header(level, title, Attr(classes=["doc-group"]))

    def render_description(self) -> BlockContent:
        """
        Render the description of the section

        Markup and Styling
        ------------------

        | HTML Elements     | CSS Selector                            |
        |:------------------|:----------------------------------------|
        | `<div><p>`{.html} | `.doc-index .doc-description > p`{.css} |
        """
        return Div(self.section.desc, Attr(classes=["doc-description"]))

    def render_body(self) -> BlockContent:
        """
        Render the body of the section

        Markup and Styling
        ------------------
        The output structure depends on the [](`~RenderReferenceSection.layout_format`):

        | Layout Format| HTML Elements    | CSS Selector                          |
        |:-------------|:-----------------|:--------------------------------------|
        | List         | `<dl>`{.html}    | `.doc-index .doc-group > dl`{.css}    |
        | Table        | `<table>`{.html} | `.doc-index .doc-group > table`{.css} |
        """
        if not self.section.contents:
            return

        from . import get_render_type

        render_objs: list[RenderObjType] = [
            get_render_type(c)(c, self.renderer)  # pyright: ignore[reportCallIssue,reportArgumentType]
            for c in self.section.contents
        ]
        rows = [row for r in render_objs for row in r.render_summary()]
        items = (
            DefinitionList(rows)
            if self.layout_format == "list"
            else str(tabulate(rows, tablefmt="grid"))
        )
        return items


class RenderReferenceSection(__RenderReferenceSection):
    """
    Extend rendering of a section on the api-reference page
    """
