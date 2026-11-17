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

    from great_docs.pandoc.blocks import DefinitionItem

    from .. import content
    from .._settings import Settings
    from ..api_reference import APIReference
    from ._renderers import Renderers


def _default_renderers() -> Renderers:
    from ._renderers import Renderers

    return Renderers()


@dataclass
class BaseRenderer(Block):
    """
    Common presentation state for documentation objects, pages and sections
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
    """The depth of the object in the documentation"""

    show_title: bool = True
    """Whether to show the title of the object"""

    show_description: bool = True
    """
    Whether to show the description of the object
    """

    show_body: bool = True
    """Whether to show the documentation body of the object"""

    renderers: Renderers = field(default_factory=_default_renderers, kw_only=True)
    """Renderer choices shared with nested objects, pages and summaries"""

    settings: Settings = field(kw_only=True)
    """
    The settings of the API reference being rendered

    A renderer reads the language, signature style and source
    links of its reference here.
    """

    def __post_init__(self):
        """
        Makes it possible for sub-classes to extend the method
        """

    def __str__(self):
        """
        Return the documentation as quarto markdown
        """
        return str(
            Blocks(
                [
                    self.title if self.show_title else None,
                    self.description if self.show_description else None,
                    self.body if self.show_body else None,
                ]
            )
        )

    @cached_property
    def title(self) -> BlockContent:
        """
        The title/header of a docstring, including any anchors

        Do not override this property.
        """
        return self.render_title()

    @cached_property
    def description(self) -> BlockContent:
        """
        A short description that the documented object

        What is consider as the description depends on the kind of object.

        Do not override this property.
        """
        return self.render_description()

    @cached_property
    def body(self) -> BlockContent:
        """
        The body that the documented object

        Do not override this property.
        """
        return self.render_body()

    @cached_property
    def summary(self) -> Sequence[DefinitionItem]:
        """
        The summary of the documented object

        Do not override this property.
        """
        return self.render_summary()

    def render_title(self) -> BlockContent:
        """
        Render the header of a docstring, including any anchors
        """

    def render_description(self) -> BlockContent:
        """
        Render the description of the object
        """

    def render_body(self) -> BlockContent:
        """
        Render the body of the object being documented
        """

    @property
    def summary_name(self) -> str:
        """
        The name of object as it will appear in the summary table
        """
        return ""

    def render_summary(self) -> Sequence[DefinitionItem]:
        """
        Return a line item, or items, that summarises the object
        """
        return []
