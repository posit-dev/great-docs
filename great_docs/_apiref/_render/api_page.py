from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, cast

from great_docs._apiref._render.mixin_page import RenderPageMixin
from great_docs._website.seo.description import metadata_value
from great_docs.pandoc.blocks import (
    BlockContent,
    Blocks,
    DefinitionItem,
    Meta,
)
from great_docs.pandoc.inlines import Link

from .._format import markdown_escape
from .base import RenderBase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..content import Page
    from .doc import RenderDoc


# Member headings render at `h3`, so the table of contents must reach depth 3
# to list them.
_MIN_MEMBER_TOC_DEPTH = 3

# Use the default site depth when the caller does not provide the merged value.
_DEFAULT_SITE_TOC_DEPTH = 2


@dataclass
class __RenderAPIPage(RenderPageMixin, RenderBase):
    """
    Render an API page object (`content.Page`)
    """

    toc_depth: int = _DEFAULT_SITE_TOC_DEPTH
    """Merged site `toc-depth` used to select a page override"""

    def __post_init__(self):
        self.page = cast("Page", self.node)
        """Page in the documentation"""

        self.path = f"{self.page.path}.qmd"
        """All objects on this page are rendered at this path"""

    @property
    def _has_one_object(self):
        return len(self.page.contents) == 1

    @cached_property
    def render_objs(self):
        """
        Render objects on the API page
        """
        from . import get_render_type

        level = self.level if self._has_one_object else self.level + 1
        render_objs: list[RenderDoc] = [
            get_render_type(c)(
                c,
                level,
                page_path=self.path,
                settings=self.settings,
            )
            for c in self.page.contents
        ]

        # For a top level object, the title will be created by
        # this api-page as front-matter, rather than a regular header.
        # Suppress the inner object's title to avoid a duplicate heading
        # alongside the Quarto-rendered front-matter title.
        for obj in render_objs:
            if obj.level == 1:
                obj.show_title = False

        return render_objs

    def render_metadata(self) -> BlockContent:
        # Derive the title of the page from the first (top-level) object
        obj = self.render_objs[0]
        title = obj._title  # pyright: ignore[reportPrivateUsage]
        metadata: dict[str, object] = {
            "title": f"{title}",
            "body-classes": "doc-api-page doc-py-api-page",
            "shift-heading-level-by": 0,
            # Disabling breadcrumbs lets Quarto use the page title in the narrow-screen
            # navigation bar; CSS adds the prefix for the reference type.
            "bread-crumbs": False,
        }
        # Add a page override only when the site depth excludes members.
        if self.toc_depth < _MIN_MEMBER_TOC_DEPTH:
            metadata["toc-depth"] = _MIN_MEMBER_TOC_DEPTH
        summary = self.page.summary
        if description := metadata_value(summary.desc if summary else obj.docstring_subject):
            metadata["description-meta"] = description
        return Meta(metadata)

    def render_body(self) -> BlockContent:
        """
        Render the body of the documentation page
        """
        return Blocks(self.render_objs)

    def render_summary(self) -> Sequence[DefinitionItem]:
        page = self.page
        if page.summary is not None:
            link = Link(markdown_escape(page.summary.name), self.path)
            items = [(str(link), page.summary.desc)]
        elif len(page.contents) > 1 and not page.flatten:
            msg = (
                f"Cannot summarize page {page.path}. "
                "Either set its `summary` attribute with name and"
                "description details, or set `flatten` to True."
            )
            raise ValueError(msg)
        else:
            items = [row for d in self.render_objs for row in d.render_summary()]
        return items


class RenderAPIPage(__RenderAPIPage):
    """
    Extension point for the rendering of an API page
    """
