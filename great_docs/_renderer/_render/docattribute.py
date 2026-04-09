from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from ..pandoc.blocks import Blocks, Div
from ..pandoc.components import Attr
from ..pandoc.inlines import Code
from .doc import RenderDoc

if TYPE_CHECKING:
    import griffe as gf

    from .. import layout
    from ..pandoc.blocks import BlockContent


@dataclass
class __RenderDocAttribute(RenderDoc):
    """
    Render documentation for an attribute (layout.DocAttribute)
    """

    show_signature_annotation: bool = True

    def __post_init__(self):
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: layout.DocAttribute = self.doc
        self.obj: gf.Attribute = self.obj

        self.subject_above_signature = self.subject_above_signature is None and not self.contained

    def render_signature(self) -> BlockContent:
        name = self.signature_name if self.show_signature_name else ""
        annotation = self.obj.annotation if self.show_signature_annotation else None
        default = getattr(self.obj, "value", None)

        # For a TypeAlias, the name is the title and we can do without the annotation
        if "type" in self.kind:
            name, annotation = None, None

        term = self.render_variable_definition(name, annotation, default)
        return Div(
            Code(str(term)).html,
            Attr(classes=["doc-signature", f"doc-{self.kind}"]),
        )

    def render_description(self) -> BlockContent:
        """
        Render description for attributes: subject above signature, no Usage label.
        """
        return Blocks(
            [
                self.render_docstring_subject(),
                self.render_signature() if self.show_signature else None,
            ]
        )

    @cached_property
    def docstring_sections_content(self):
        """
        Filter out Returns sections for properties since the type
        is already shown in the signature.
        """
        items = super().docstring_sections_content
        return [(title, section) for title, section in items if title != "Returns"]


class RenderDocAttribute(__RenderDocAttribute):
    """
    Extend Rendering of a layout.DocAttribute object
    """
