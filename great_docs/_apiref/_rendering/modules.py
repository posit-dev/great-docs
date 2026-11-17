"""Presentation of modules, with a name declaration and member groups"""

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
    The presentation of a module, with a name declaration and member groups

    The description shows the name declaration, then the Usage and source row and
    the subject. The body shows the docstring sections followed by member groups.
    A module's signature is its name, without parameters.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to module documentation"""
        super().__post_init__()
        self.doc: content.DocModule = self.doc
        self.obj: gf.Module = self.obj

    def render_signature(self) -> BlockContent:
        """Render the module name declaration, or return `None` for an empty name"""
        if not self.signature_name:
            return None
        return Div(
            Code(self.signature_name),
            Attr(classes=["doc-signature", f"doc-{self.kind_slug}"]),
        )
