"""
Presentation of PEP 695 type aliases

An alias shows its declaration in source form, with its type parameters and value,
and keeps its docstring sections. PEP 613 aliases render as attributes instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import griffe as gf

from great_docs.pandoc.blocks import Blocks, Div
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code, Inlines0, Span

from .._format import HAS_RUFF, format_value, render_formatted_expr
from ._type_parameters import render_type_parameters
from .objects import ObjectRenderer

if TYPE_CHECKING:
    from great_docs.pandoc.blocks import BlockContent
    from great_docs.pandoc.inlines import InlineContentItem

    from .. import content


@dataclass
class TypeAliasRenderer(ObjectRenderer):
    """
    The presentation of a PEP 695 type alias, with its type parameters and value

    The description shows the subject, then the declaration in source form, without
    a Usage row. A generic alias renders its `Type Parameters` section even though it
    is not callable.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to type alias documentation"""
        super().__post_init__()
        self.doc: content.DocTypeAlias = self.doc
        self.obj: gf.TypeAlias = self.obj

    def _render_value(self, value: str | gf.Expr) -> str:
        """
        Format an alias value with normalised string quotes and syntax highlighting

        When ruff is available, it wraps long expressions; other values use the
        ordinary inline markup.
        """
        if not isinstance(value, gf.Expr):
            return format_value(value)
        if HAS_RUFF and len(str(value)) > 79:
            return render_formatted_expr(value)
        return self.render_annotation(value)

    def render_signature(self) -> BlockContent:
        """
        Render the alias in its source form, e.g. `type Pair[T] = tuple[T, T]`
        """
        name = self.signature_name
        declared = f"{name}{render_type_parameters(self.obj.type_parameters)}"

        items: list[InlineContentItem] = [
            Span("type", Attr(classes=[f"doc-{self.kind_slug}-keyword", "kw"])),
            " ",
            Span(declared, Attr(classes=["doc-parameter-name"])),
        ]

        value = self.obj.value
        if value is not None:
            items.extend(
                [
                    " ",
                    Span("=", Attr(classes=["doc-parameter-default-sep", "op"])),
                    " ",
                    Span(self._render_value(value), Attr(classes=["doc-parameter-default"])),
                ]
            )

        return Div(
            Code(str(Inlines0(items))).html,
            Attr(classes=["doc-signature", f"doc-{self.kind_slug}"]),
        )

    def render_description(self) -> BlockContent:
        """Render the subject followed by the alias declaration, without a Usage row"""
        return Blocks(
            [
                self.render_docstring_subject(),
                self.signature,
            ]
        )

    def render_type_parameters_section(self, el: gf.DocstringSectionTypeParameters) -> BlockContent:
        """Render a `Type Parameters` section for a generic alias"""
        return self.render_definition_items(el)
