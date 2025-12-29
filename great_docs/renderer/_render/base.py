from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from quartodoc.pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
)

from .extending import extend_base_class

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quartodoc import layout

    from .. import Renderer
    from ..typing import SummaryItem


@dataclass
class __RenderBase(Block):
    """
    Render an object
    """

    layout_obj: (
        layout.DocClass
        | layout.DocFunction
        | layout.DocAttribute
        | layout.DocModule
        | layout.Page
        | layout.Section
        | layout.Link
        | layout.Layout
    )
    """Layout object to be documented"""

    renderer: Renderer
    """Renderer that holds the configured values"""

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

    def __post_init__(self):
        """
        Makes it possible for sub-classes to extend the method
        """

    def __str__(self):
        """
        The documentation as quarto markdown
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
    def summary(self) -> Sequence[SummaryItem]:
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

    def render_summary(self) -> Sequence[SummaryItem]:
        """
        Return a line(s) item that summarises the object
        """
        return []


class RenderBase(__RenderBase):
    """
    Extend the base render class

    This class is meant for internal use. Users should not have
    to extend it.
    """

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # We want users to extend the rendering by subclassing a Render*
        # class and overriding methods and/or attributes as necessary.
        #
        # This hook customises how user-defined Render subclasses behave.
        #
        # The package defines a set of empty base classes—extension points,
        # which contain no methods or attributes by default. Users are
        # encouraged to subclass a provided Render class and override these
        # extension points with their own methods and attributes.
        #
        # Internally, we also subclass these empty base classes. This ensures
        # that any user-defined overrides "fill in" the base and are used
        # throughout the package.
        #
        # The "filling in" should only happen when extending the Render*
        # classes outside the package.
        if cls.__module__[:10] != "great_docs":
            extend_base_class(cls)
