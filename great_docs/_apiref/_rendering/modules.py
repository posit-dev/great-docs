"""Module documentation with grouped member presentation"""

from __future__ import annotations

from typing import TYPE_CHECKING

from great_docs.pandoc.blocks import Div
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code

from .members import MembersRendererMixin
from .objects import ObjectRenderer

if TYPE_CHECKING:
    import griffe as gf

    from great_docs.pandoc.blocks import BlockContent

    from .. import content


class ModuleRenderer(MembersRendererMixin, ObjectRenderer):
    """
    Module documentation with grouped member presentation
    """

    def __post_init__(self):
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: content.DocModule = self.doc
        self.obj: gf.Module = self.obj

    # TODO: Verify that this is really required.
    # Why isn't the header/title enough?
    def render_signature(self) -> BlockContent:
        if not self.signature_name:
            return None
        return Div(
            Code(self.signature_name),
            Attr(classes=["doc-signature", f"doc-{self.kind_slug}"]),
        )
