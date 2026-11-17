"""
Presentation of attributes, properties and PEP 613 type aliases

The declaration and value follow the subject. A `Returns` section is omitted, and
only properties show `Raises`, `Warns`, `Yields` and `Receives` sections.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from great_docs.pandoc.blocks import Blocks, Div
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code

from ._context import _RenderingPurpose
from .objects import ObjectRenderer

if TYPE_CHECKING:
    import griffe as gf

    from great_docs._apiref.typing import DocstringSectionWithDefinitions
    from great_docs.pandoc.blocks import BlockContent

    from .. import content


@dataclass
class AttributeRenderer(ObjectRenderer):
    """
    The presentation of an attribute or property, with its annotation and value

    The description shows the subject, then the declaration, without a Usage row.
    On a typing-variable page the declaration leaves out the name, which the page
    already shows, and a PEP 613 type alias leaves out its `TypeAlias` annotation.
    Only properties show `Raises`, `Warns`, `Yields` and `Receives` sections.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to attribute documentation"""
        super().__post_init__()
        self.doc: content.DocAttribute = self.doc
        self.obj: gf.Attribute = self.obj

    def render_signature(self) -> BlockContent:
        """
        Render the declaration with the omissions that typing pages need

        A typing-variable page leaves out the name, and a type alias leaves out its
        `TypeAlias` annotation.
        """
        name = "" if self._purpose is _RenderingPurpose.TYPE_VARIABLE else self.signature_name
        annotation = None if self._purpose is _RenderingPurpose.TYPE_ALIAS else self.obj.annotation
        default = getattr(self.obj, "value", None)

        term = self.render_variable_definition(name, annotation, default)
        return Div(
            Code(str(term)).html,
            Attr(classes=["doc-signature", f"doc-{self.kind_slug}"]),
        )

    def render_description(self) -> BlockContent:
        """Render the subject followed by the declaration, without a Usage row"""
        return Blocks(
            [
                self.render_docstring_subject(),
                self.signature,
            ]
        )

    @cached_property
    def docstring_sections_content(self):
        """
        The docstring sections without `Returns`

        The declaration already shows the property's or attribute's annotation.
        """
        items = super().docstring_sections_content
        return [(title, section) for title, section in items if title != "Returns"]

    def _render_property_only_section(self, el: DocstringSectionWithDefinitions) -> BlockContent:
        """
        Render a `Raises`, `Warns`, `Yields` or `Receives` section only for a property

        A property runs code on access, so it can raise or yield. A plain attribute
        cannot, so its section is omitted with a warning. The check uses Griffe's
        `property` label rather than the kind label, which can classify a property by
        a return annotation such as `TypeVar` instead.
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
