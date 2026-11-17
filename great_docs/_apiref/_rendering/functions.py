"""Function documentation with callable signatures and sections"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .callables import CallableRendererMixin
from .objects import ObjectRenderer

if TYPE_CHECKING:
    import griffe as gf

    from .. import content


class FunctionRenderer(CallableRendererMixin, ObjectRenderer):
    """
    Function documentation with callable signatures and sections
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: content.DocFunction = self.doc
        self.obj: gf.Function = self.obj
