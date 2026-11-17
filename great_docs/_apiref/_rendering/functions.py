"""Presentation of functions and methods"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .callables import CallableRendererMixin
from .objects import ObjectRenderer

if TYPE_CHECKING:
    import griffe as gf

    from .. import content


class FunctionRenderer(CallableRendererMixin, ObjectRenderer):
    """
    The presentation of a function or method, with its signature and docstring sections

    The description shows the subject, then the Usage and source row and the
    signature; the docstring body follows. Override the signature or section methods
    to change how they render; the prepared documentation stays unchanged.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to function documentation"""
        super().__post_init__()
        self.doc: content.DocFunction = self.doc
        self.obj: gf.Function = self.obj
