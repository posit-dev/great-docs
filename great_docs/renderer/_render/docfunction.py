from __future__ import annotations

from typing import TYPE_CHECKING

from .doc import RenderDoc
from .mixin_call import RenderDocCallMixin

if TYPE_CHECKING:
    import griffe as gf
    from quartodoc import layout


class __RenderDocFunction(RenderDocCallMixin, RenderDoc):
    """
    Render documentation for a function (layout.DocFunction)
    """

    def __post_init__(self):
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: layout.DocFunction = self.doc
        self.obj: gf.Function = self.obj

        self.subject_above_signature = self.subject_above_signature is None and not self.contained


class RenderDocFunction(__RenderDocFunction):
    """
    Extend Rendering of a layout.DocFunction object
    """
