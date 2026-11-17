"""PEP 695 alias documentation with source-form declarations"""

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
    PEP 695 alias documentation with source-form declarations
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: content.DocTypeAlias = self.doc
        self.obj: gf.TypeAlias = self.obj

    def _render_value(self, value: str | gf.Expr) -> str:
        """
        Format an alias value the way `render_variable_definition` formats an
        annotation: ruff-format only when it is worth invoking ruff for (long
        expressions), otherwise the plain recursive render, which also
        normalizes string-literal quotes and highlights them
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
        """
        Render description for type aliases: subject above signature, no Usage label
        """
        return Blocks(
            [
                self.render_docstring_subject(),
                self.signature,
            ]
        )

    def render_type_parameters_section(self, el: gf.DocstringSectionTypeParameters) -> BlockContent:
        """
        Render a `Type Parameters` section

        A type alias can be generic without being callable, so it needs its
        own renderer rather than inheriting one from the call mixin.
        """
        return self.render_definition_items(el)
