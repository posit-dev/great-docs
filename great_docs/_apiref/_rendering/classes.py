"""
Presentation of classes and dataclasses

A class shows its constructor signature, docstring sections and member groups. A
dataclass documents each field once, as a constructor parameter, rather than again
as an attribute.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import griffe as gf

from great_docs._translations import translate
from great_docs.pandoc.blocks import BlockContent, Blocks, Div, Para
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code, Link, Span, join_inline_content

from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .callables import CallableRendererMixin
from .members import MembersRendererMixin
from .objects import ObjectRenderer

if TYPE_CHECKING:
    from .. import content


class ClassRenderer(MembersRendererMixin, CallableRendererMixin, ObjectRenderer):
    """
    The presentation of a class, with its constructor signature and member groups

    The description shows the subject, then the Usage and source row and the
    constructor signature, followed by the direct bases when enabled. The body
    shows the docstring sections followed by member groups. For a dataclass
    without an authored `Parameters` or `Attributes` section, the renderer generates
    `Parameter Attributes` and
    `Init Parameters` sections from the constructor parameters.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to class documentation"""
        super().__post_init__()
        self.doc: content.DocClass = self.doc
        self.obj: gf.Class = self.obj

    def __str__(self) -> str:
        """Compose the class documentation with its published link target"""
        rendered = super().__str__()
        if not self.settings.show_bases or not self.doc.anchor:
            return rendered
        # The inventory's qualified anchor is independent of custom headings and descriptions.
        anchor = Div(attr=Attr(identifier=self.doc.anchor))
        return str(Blocks([anchor, rendered]))

    def render_description(self) -> BlockContent:
        """Render the class description followed by the direct base classes"""
        description = super().render_description()
        bases = self.render_bases()
        return Blocks([description, bases]) if bases is not None else description

    def render_bases(self) -> BlockContent:
        """
        Render direct base classes when the reference enables them

        Returns
        -------
        :
            A paragraph with links to documented bases, or `None` when there are
            no visible bases or the setting is off.
        """
        if not self.settings.show_bases:
            return None
        bases = [rendered for base in self.obj.bases if (rendered := self._render_base(base))]
        if not bases:
            return None
        label = translate("base_classes", self.settings.lang)
        label_span = Span(f"{label}:", Attr(classes=["doc-class-bases"]))
        return Para([label_span, join_inline_content(bases, sep=", ")])

    def _render_base(self, base: gf.Expr | str) -> Link | Code | None:
        label = base.rpartition(".")[2] if isinstance(base, str) else str(base)
        unlinked = Code(label, Attr(classes=["gd-no-link"]))
        base_name = _expression_name(base)
        if base_name is None:
            return unlinked

        path = base_name if isinstance(base_name, str) else base_name.canonical_path
        if path in {"object", "builtins.object"}:
            return None

        spelling = str(base_name)
        private = spelling.rpartition(".")[2].startswith("_") or path.rpartition(".")[2].startswith(
            "_"
        )
        target = self.extension.class_targets.get(path)
        if target is not None and target.uri:
            name = target.obj.name
            canonical_name = target.obj.canonical_path.rpartition(".")[2]
            if (private or canonical_name.startswith("_")) and not name.startswith("_"):
                label = name + (
                    label[len(spelling) :] if isinstance(base, gf.ExprSubscript) else ""
                )
            return Link(Code(label), f"/{target.uri.lstrip('/')}")
        if private:
            return None
        return unlinked

    @cached_property
    def is_dataclass(self):
        """
        Whether the class object is a dataclass
        """
        return "dataclass" in self.obj.labels

    @cached_property
    def docstring_sections_content(self):
        """
        The docstring sections, with generated sections for a dataclass's fields

        Nothing is added when an authored `Parameters` or `Attributes` section already
        documents the fields. Otherwise the `Parameter Attributes` and `Init Parameters`
        sections go after the leading text and before the other sections.
        """
        items = super().docstring_sections_content
        titles = set(item[0] for item in items)
        # Authored field sections already cover the same dataclass parameters.
        if (
            not self.is_dataclass
            or "Parameters" in titles
            or "Attributes" in titles
            or not len(self.parameters)
        ):
            return items

        # Create and insert Parameter Attributes
        idx = 1 if items and items[0][0] == "Text" else 0
        if len(self.parameter_attributes):
            lst = [
                gf.DocstringParameter(
                    p.name,
                    description=p.docstring.value if p.docstring else "",
                    annotation=p.annotation,
                    value=p.default,
                )
                for p in self.parameter_attributes
            ]
            params = DCDocstringSectionParameterAttributes(lst, "Parameter Attributes")
            items.insert(idx, (params.title, params))
            idx += 1

        # Create and insert Init Parameters
        if len(self.init_parameters):
            lst = [
                gf.DocstringParameter(
                    p.name,
                    description=p.docstring.value if p.docstring else "",
                    annotation=p.annotation,
                    value=p.default,
                )
                for p in self.init_parameters
            ]
            params = DCDocstringSectionInitParameters(lst, "Init Parameters")
            items.insert(idx, (params.title, params))

        return items

    @cached_property
    def parameter_attributes(self) -> gf.Parameters:
        """
        The dataclass's signature parameters that are also annotated attributes

        An ordinary class has none.
        """
        if not self.is_dataclass:
            return gf.Parameters()

        lst = [
            p for p in self.parameters if p.name in self.obj.attributes and p.annotation is not None
        ]
        return gf.Parameters(*lst)

    @cached_property
    def init_parameters(self) -> gf.Parameters:
        """
        The dataclass's signature parameters that are not attributes

        An ordinary class has none.
        """
        if not self.is_dataclass:
            return gf.Parameters()

        lst = [p for p in self.parameters if p.name not in self.obj.attributes]
        return gf.Parameters(*lst)


def _expression_name(expression: gf.Expr | str) -> gf.ExprName | gf.ExprAttribute | str | None:
    """
    Extract a bare or dotted name from a Griffe expression

    Examples
    --------
    Griffe expressions are shown in their source spelling.
    Quoted values are strings.

    ```text
    Base            -> Base
    pkg.Base        -> pkg.Base
    pkg.Base[T]     -> pkg.Base
    factory()       -> None
    factory().Base  -> None
    "pkg.Base"      -> "pkg.Base"
    ```
    """
    if isinstance(expression, str):
        return expression
    expression = expression.left if isinstance(expression, gf.ExprSubscript) else expression
    if isinstance(expression, gf.ExprName) or (
        isinstance(expression, gf.ExprAttribute)
        and all(isinstance(part, gf.ExprName) for part in expression.values)
    ):
        return expression
    return None
