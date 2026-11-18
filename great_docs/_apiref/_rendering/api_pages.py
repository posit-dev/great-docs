"""
API pages, with their front matter, objects and summary rows

A page with one object renders it at the page's heading level; a page with several
renders each one level deeper.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, cast

from great_docs._apiref._rendering.pages import PageRendererMixin
from great_docs._content.metadata import metadata_value
from great_docs.pandoc.blocks import (
    BlockContent,
    Blocks,
    DefinitionItem,
    Meta,
)
from great_docs.pandoc.inlines import Link

from .._format import markdown_escape
from ._context import _RenderingPurpose, output_page_path
from .base import BaseRenderer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..content import Page
    from .objects import ObjectRenderer


# Member headings render at `h3`, so the table of contents must reach depth 3
# to list them.
_MIN_MEMBER_TOC_DEPTH = 3

# Use the default site depth when the caller does not provide the merged value.
_DEFAULT_SITE_TOC_DEPTH = 2


@dataclass
class APIPageRenderer(PageRendererMixin, BaseRenderer):
    """
    An API page that documents one or more prepared Python objects

    The page title in the front matter comes from the first object. A page with one
    object omits that object's heading, which would repeat the title; a page with
    several keeps each object's heading, one level deeper. The page's summary rows
    come from its authored summary or from its objects' own rows.
    """

    toc_depth: int = _DEFAULT_SITE_TOC_DEPTH
    """Merged site `toc-depth` used to select a page override"""

    def __post_init__(self) -> None:
        """Set the page's summary-link path and the output-relative path its objects report"""
        self.page = cast("Page", self.node)
        """Page in the documentation"""

        self.path = f"{self.page.path}{self.settings.out_page_suffix}"
        """The page's path relative to the reference directory, used in summary links"""

        self.context_page_path = output_page_path(
            Path(self.settings.dir) / self.path, self.output_root
        )
        """The page's path relative to the output directory, which its objects' `context` reports"""

    @property
    def _has_one_object(self) -> bool:
        """Whether the page contains exactly one documented object"""
        return len(self.page.contents) == 1

    @cached_property
    def object_renderers(self) -> list[ObjectRenderer]:
        """The renderers of the page's objects, which share the page's context"""
        level = self.level if self._has_one_object else self.level + 1
        return [
            self.make_renderer(c, level, page_path=self.path, _purpose=_RenderingPurpose.API_PAGE)
            for c in self.page.contents
        ]

    def render_metadata(self) -> BlockContent:
        # Derive the title of the page from the first (top-level) object
        """
        Render the page front matter from the first object's title and the page summary

        The description comes from the authored summary, or else the first object's
        subject. The page raises `toc-depth` only when the site setting would hide
        members.

        Returns
        -------
        :
            The front matter.
        """
        obj = self.object_renderers[0]
        title = obj.title_content
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
        Render the page's objects in their authored order

        Returns
        -------
        :
            The objects' documentation.
        """
        return Blocks(self.object_renderers)

    def render_summary(self) -> Sequence[DefinitionItem]:
        """
        Render the page's authored summary row, or else its objects' own summary rows

        Summaries do not render object bodies.

        Returns
        -------
        :
            One linked row from the authored summary, or the rows of the page's objects.

        Raises
        ------
        ValueError
            If the page has several objects and neither a summary nor `flatten` set.
        """
        page = self.page
        if page.summary is not None:
            link = Link(markdown_escape(page.summary.name), self.path)
            items = [(str(link), page.summary.desc)]
        elif len(page.contents) > 1 and not page.flatten:
            msg = (
                f"Cannot summarise page {page.path}. "
                "Either set its `summary` attribute with name and"
                "description details, or set `flatten` to True."
            )
            raise ValueError(msg)
        else:
            items = [row for d in self.object_renderers for row in d.render_summary()]
        return items
