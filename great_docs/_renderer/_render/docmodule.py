from __future__ import annotations

from typing import TYPE_CHECKING

from ..pandoc.blocks import Div
from ..pandoc.components import Attr
from ..pandoc.inlines import Code
from .doc import RenderDoc
from .mixin_members import RenderDocMembersMixin

if TYPE_CHECKING:
    import griffe as gf

    from .. import layout
    from ..pandoc.blocks import BlockContent


class __RenderDocModule(RenderDocMembersMixin, RenderDoc):
    """
    Render documentation for a module (layout.DocModule)
    """

    def __post_init__(self):
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: layout.DocModule = self.doc
        self.obj: gf.Module = self.obj

    # TODO: Verify that this is really required.
    # Why isn't the header/title enough?
    def render_signature(self) -> BlockContent:
        if not self.signature_name:
            return None
        return Div(
            Code(self.signature_name),
            Attr(classes=["doc-signature", f"doc-{self.kind}"]),
        )


class RenderDocModule(__RenderDocModule):
    """
    Extend Rendering of a layout.DocModule object
    """
