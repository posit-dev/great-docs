"""Attribute and property documentation with values and annotations"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from great_docs.pandoc.blocks import Blocks, Div
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code

from .objects import ObjectRenderer

if TYPE_CHECKING:
    import griffe as gf

    from great_docs._apiref.typing import DocstringSectionWithDefinitions
    from great_docs.pandoc.blocks import BlockContent

    from .. import content


@dataclass
class AttributeRenderer(ObjectRenderer):
    """
    Attribute and property documentation with values and annotations
    """

    show_signature_annotation: bool = True

    def __post_init__(self):
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: content.DocAttribute = self.doc
        self.obj: gf.Attribute = self.obj

        self.subject_above_signature = self.subject_above_signature is None and not self.contained

    def render_signature(self) -> BlockContent:
        name = self.signature_name if self.show_signature_name else ""
        annotation = self.obj.annotation if self.show_signature_annotation else None
        default = getattr(self.obj, "value", None)

        term = self.render_variable_definition(name, annotation, default)
        return Div(
            Code(str(term)).html,
            Attr(classes=["doc-signature", f"doc-{self.kind_slug}"]),
        )

    def render_description(self) -> BlockContent:
        """
        Render description for attributes: subject above signature, no Usage label
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
        The docstring sections, excluding Returns for properties since the type
        is already shown in the signature
        """
        items = super().docstring_sections_content
        return [(title, section) for title, section in items if title != "Returns"]

    def _render_property_only_section(self, el: DocstringSectionWithDefinitions) -> BlockContent:
        """
        Render a section that only makes sense for a property

        A property runs code on access, so it can legitimately document
        `Raises`, `Warns`, or a `Yields`/`Receives` pair. A plain data
        attribute cannot, so it falls through to the unhandled-section path
        instead of rendering. Gate on the griffe fact (`"property" in
        obj.labels`) rather than `self.label`: `get_label` runs annotation
        heuristics (`TypeVar`, `TypeAlias`, ...) before it checks for the
        `property` label, so a property with such a return annotation would
        otherwise be misidentified as not a property.
        """
        if "property" not in self.obj.labels:
            return self._unhandled_section(el)
        return self.render_definition_items(el)

    def render_raises_section(self, el: gf.DocstringSectionRaises) -> BlockContent:
        """Render a `Raises` section on a property"""
        return self._render_property_only_section(el)

    def render_warns_section(self, el: gf.DocstringSectionWarns) -> BlockContent:
        """Render a `Warns` section on a property"""
        return self._render_property_only_section(el)

    def render_yields_section(self, el: gf.DocstringSectionYields) -> BlockContent:
        """Render a `Yields` section on a property"""
        return self._render_property_only_section(el)

    def render_receives_section(self, el: gf.DocstringSectionReceives) -> BlockContent:
        """Render a `Receives` section on a property"""
        return self._render_property_only_section(el)
