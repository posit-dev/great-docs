"""Common state and cached presentation for object, page and section renderers"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from great_docs.pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from great_docs.pandoc.blocks import DefinitionItem

    from .. import content
    from .._customisation import Extension
    from .._settings import Settings
    from ..api_reference import APIReference
    from ._renderers import Renderers


def _default_renderers() -> Renderers:
    """Create independent default choices for a directly constructed renderer"""
    from ._renderers import Renderers

    return Renderers()


@dataclass
class BaseRenderer(Block):
    """
    The common base of object, page and section renderers

    An object renderer renders a heading and a docstring; a page renderer renders
    front matter and the objects on the page; a section renderer renders linked
    summaries. Each renderer renders its title, description, body and summary once
    and caches them. To change one, override the matching `render_*` method, and
    return `None` from a method that renders a block to omit that block.
    """

    node: (
        APIReference
        | content.DocClass
        | content.DocFunction
        | content.DocAttribute
        | content.DocTypeAlias
        | content.DocModule
        | content.Page
        | content.Section
    )
    """The node being documented"""

    level: int = 1
    """The heading depth of this appearance"""

    renderers: Renderers = field(default_factory=_default_renderers, kw_only=True)
    """Renderer choices shared with nested objects, pages and summaries"""

    extension: Extension | None = field(default=None, kw_only=True)
    """The extension that supplies project context"""

    output_root: Path | None = field(default=None, kw_only=True)
    """The documentation output root, or `None` outside a known build"""

    context_page_path: str | None = field(default=None, kw_only=True)
    """The containing page's path relative to the output directory, apart from summary links"""

    settings: Settings = field(kw_only=True)
    """
    The settings of the API reference being rendered

    A renderer reads the language, signature style and source
    links of its reference here.
    """

    def __post_init__(self) -> None:
        """End the chain of `super().__post_init__()` calls from subclasses and mixins"""

    def __str__(self) -> str:
        """Compose the cached title, description and body as Quarto Markdown"""
        return str(
            Blocks(
                [
                    self.title,
                    self.description,
                    self.body,
                ]
            )
        )

    @cached_property
    def title(self) -> BlockContent:
        """
        The title, rendered once per renderer and cached

        Override `render_title` to change it. An object's title is a visible heading
        and a page's title is front matter. `None` omits the title.
        """
        return self.render_title()

    @cached_property
    def description(self) -> BlockContent:
        """
        The description, rendered once per renderer and cached

        Override `render_description` to change it. Each kind of object sets its own
        order for the signature and the docstring's opening line. `None` omits the
        description.
        """
        return self.render_description()

    @cached_property
    def body(self) -> BlockContent:
        """
        The body, rendered once per renderer and cached

        Override `render_body` to change it. An object renderer may follow the object's
        docstring with automatic member groups. `None` omits the body.
        """
        return self.render_body()

    @cached_property
    def summary(self) -> Sequence[DefinitionItem]:
        """
        The linked summary items, rendered once per renderer and cached

        Override `render_summary` to change them. An empty sequence omits the summary
        rows but keeps the objects in the reference and its inventory.
        """
        return self.render_summary()

    def render_title(self) -> BlockContent:
        """Render an object's heading or a page's front matter, or return `None` to omit it"""

    def render_description(self) -> BlockContent:
        """Render the description, or return `None` to omit it"""

    def render_body(self) -> BlockContent:
        """Render the body, or return `None` to omit it"""

    @property
    def summary_name(self) -> str:
        """The label in linked summaries, which the base renderer leaves empty"""
        return ""

    def render_summary(self) -> Sequence[DefinitionItem]:
        """Render linked summary items, or return an empty sequence to omit them"""
        return []
