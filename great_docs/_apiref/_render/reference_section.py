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
from .base import RenderBase

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
class __RenderReferenceSection(RenderBase):
    """
    Render a section object (`content.Section`)

    This is a section of the index/reference page
    """

    display_format: Literal["list", "table"] = "list"

    def __post_init__(self):
        self.section = cast("Section", self.node)
        """Section of the reference page"""

    def render_title(self) -> BlockContent:
        """
        Render the title or subtitle of section

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
        key = _GROUP_TITLE_KEYS.get(title)
        return Header(
            level,
            translate(key, self.settings.lang) if key else title,
            Attr(classes=["doc-group"]),
        )

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
        The output structure depends on the [](`~RenderReferenceSection.display_format`):

        | Display Format| HTML Elements    | CSS Selector                          |
        |:-------------|:-----------------|:--------------------------------------|
        | List         | `<dl>`{.html}    | `.doc-index .doc-group > dl`{.css}    |
        | Table        | `<table>`{.html} | `.doc-index .doc-group > table`{.css} |


        The list or table contains object names with brief descriptions.
        Each name links to the object's API reference page.

        A useful styling customization is to add parentheses to function
        and method names.

        ```css
        .doc-index .doc-group > dl dt > a.doc-function-name::after,
        .doc-index .doc-group > dl dt > a.doc-method-name::after {
          content: "()";
        }
        ```

        See Also
        --------
        great_docs.renderer.RenderDoc.render_summary : This is where the items in the
        list or table are rendered.
        """
        if not self.section.contents:
            return

        from . import get_render_type

        render_objs: list[RenderObjType] = [
            get_render_type(c)(c, settings=self.settings) for c in self.section.contents
        ]
        rows = [row for r in render_objs for row in r.render_summary()]
        items = (
            DefinitionList(rows)
            if self.display_format == "list"
            else summary_table(rows, self.settings.lang)
        )
        return items


class RenderReferenceSection(__RenderReferenceSection):
    """
    Extension point for the rendering of a section on the api-reference page
    """
