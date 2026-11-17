"""
Sections of the reference index, with their headings and summary rows

A section lists its objects or API pages as a definition list or a summary table.
Standard group titles are translated; custom titles keep their text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from great_docs._translations import translate
from great_docs.pandoc.blocks import (
    BlockContent,
    DefinitionList,
    Div,
    Header,
)
from great_docs.pandoc.components import Attr

from ._tables import summary_table
from .base import BaseRenderer

if TYPE_CHECKING:
    from typing import Literal

    from ..content import Section
    from ..typing import RenderObjType

# Translate the standard English titles used by `great-docs init` and
# preserve custom titles.
_GROUP_TITLE_KEYS = {
    "Classes": "classes",
    "Functions": "functions",
    "Methods": "methods",
}


@dataclass
class ReferenceSectionRenderer(BaseRenderer):
    """
    A section of the reference index, with a heading, description and summary rows

    The rows form a definition list unless `display_format` selects a table. An
    object whose summary row is hidden stays in the section.
    """

    display_format: Literal["list", "table"] = "list"
    """Whether the summary rows form a definition list or a table"""

    def __post_init__(self) -> None:
        """Expose the resolved section as `section`"""
        self.section = cast("Section", self.node)
        """Section of the reference page"""

    def render_title(self) -> BlockContent:
        """
        Render the section's title or subtitle as a heading

        A title is one level below the base heading level and a subtitle two levels
        below. Return `None` when the section has neither. Standard group titles are
        translated; custom titles keep their text.
        """
        if self.section.title:
            level, title = self.level + 1, self.section.title
        elif self.section.subtitle:
            level, title = self.level + 2, self.section.subtitle
        else:
            return None
        key = _GROUP_TITLE_KEYS.get(title)
        return Header(
            level,
            translate(key, self.settings.lang) if key else title,
            Attr(classes=["doc-group"]),
        )

    def render_description(self) -> BlockContent:
        """
        Render the description of the section
        """
        return Div(self.section.desc, Attr(classes=["doc-description"]))

    def render_body(self) -> BlockContent:
        """
        Render the section's summary rows as a definition list or table

        Each entry renders only its summary rows, not its body. Return `None` for an
        empty section.
        """
        if not self.section.contents:
            return

        object_renderers: list[RenderObjType] = [
            self.renderers.make(
                c,
                settings=self.settings,
                extension=self.extension,
                output_root=self.output_root,
                context_page_path=self.context_page_path,
            )
            for c in self.section.contents
        ]
        rows = [row for r in object_renderers for row in r.render_summary()]
        items = (
            DefinitionList(rows)
            if self.display_format == "list"
            else summary_table(rows, self.settings.lang)
        )
        return items
