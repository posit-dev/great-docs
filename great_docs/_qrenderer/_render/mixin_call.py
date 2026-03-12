from __future__ import annotations

import re
from functools import cached_property
from typing import TYPE_CHECKING, TypeAlias, cast

import griffe as gf

from great_docs._renderer.pandoc.blocks import (
    BlockContent,
    Blocks,
    CodeBlock,
    DefinitionItem,
    DefinitionList,
    Div,
)
from great_docs._renderer.pandoc.components import Attr
from great_docs._renderer.pandoc.inlines import Code
from great_docs._renderer.renderer import _convert_rst_text

from .._format import formatted_signature, repr_obj
from .._griffe.docstrings import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .doc import RenderDoc

if TYPE_CHECKING:
    from great_docs._renderer.layout import DocClass, DocFunction

    from ..typing import DocstringDefinitionType

# singledispatch needs this type at runtime
DocstringSectionWithDefinitions: TypeAlias = (
    gf.DocstringSectionParameters
    | gf.DocstringSectionOtherParameters
    | gf.DocstringSectionReturns
    | gf.DocstringSectionYields
    | gf.DocstringSectionReceives
    | gf.DocstringSectionRaises
    | gf.DocstringSectionWarns
    | gf.DocstringSectionAttributes
    | DCDocstringSectionParameterAttributes
    | DCDocstringSectionInitParameters
)


class __RenderDocCallMixin(RenderDoc):
    """
    Mixin to render Doc objects that can be called

    i.e. classes (for the __init__ method) and functions/methods
    """

    def __post_init__(self):
        super().__post_init__()

        self.doc = cast("DocFunction | DocClass", self.doc)  # pyright: ignore[reportUnnecessaryCast]
        self.obj = cast("gf.Function", self.obj)  # pyright: ignore[reportUnnecessaryCast]

        # Lookup for the parameter kind by name
        # gf.DocstringParameter does not have the parameter kind but the
        # rendering needs it.
        self._parameter_kinds = {p.name: p.kind for p in self.parameters}

    @RenderDoc.render_docstring_section.register  # pyright: ignore[reportFunctionMemberAccess]
    def _(self, el: DocstringSectionWithDefinitions):
        """
        Render docstring sections that have a list of definitions

        e.g. Parameters, Other Parameters, Returns, Yields, Receives,
             Warns, Attributes
        """
        _RST_DIRECTIVE_RE = re.compile(r"^\.\.\s+\w+::")

        def _is_rst_directive_item(item: DocstringDefinitionType) -> bool:
            """Check if a definition item is actually a misinterpreted RST directive."""
            ann = getattr(item, "annotation", None)
            return bool(ann and isinstance(ann, str) and _RST_DIRECTIVE_RE.match(ann.strip()))

        def render_section_item(el: DocstringDefinitionType) -> DefinitionItem:
            """
            Render a single definition in a section
            """
            name = getattr(el, "name", None) or ""
            default = getattr(el, "default", None)
            annotation = el.annotation

            # Parameter of kind *args or **kwargs have no default values
            if isinstance(el, gf.DocstringParameter) and "*" in el.name:
                default = None

            term = self.render_variable_definition(name, annotation, default)

            # Annotations are expressed in html so that contained interlink
            # references can be processed. Pandoc does not process any markup
            # within backquotes `...`, but it does if the markup is within
            # html code tags.
            desc = _convert_rst_text(el.description) if el.description else ""
            return Code(str(term)).html, desc

        normal_items: list[DefinitionItem] = []
        directive_parts: list[str] = []

        for item in el.value:
            if _is_rst_directive_item(item):
                # Reconstruct the RST directive text and convert it
                ann = item.annotation.strip()
                desc = getattr(item, "description", "") or ""
                if desc:
                    lines = desc.splitlines()
                    directive_text = ann + "\n" + "\n".join("    " + ln for ln in lines)
                else:
                    directive_text = ann
                directive_parts.append(_convert_rst_text(directive_text))
            else:
                normal_items.append(render_section_item(item))

        parts: list[BlockContent] = []
        if normal_items:
            parts.append(Div(DefinitionList(normal_items), Attr(classes=["doc-definition-items"])))
        parts.extend(directive_parts)

        if len(parts) == 1:
            return parts[0]
        return Blocks(parts) if parts else None

    @cached_property
    def parameters(self) -> gf.Parameters:
        """
        Return the parameters of the callable
        """
        from .._globals import EXCLUDE_PARAMETERS

        obj = self.obj
        parameters = obj.parameters

        exclude = EXCLUDE_PARAMETERS.get(self.obj.path, ())
        if isinstance(exclude, str):
            exclude = (exclude,)
        exclude = set(exclude)

        if not len(parameters) > 0 or not obj.parent:
            return parameters

        param = obj.parameters[0].name
        omit_first_parameter = (obj.parent.is_class and param in ("self", "cls")) or (
            obj.parent.is_module and obj.is_class and param == "self"
        )

        if omit_first_parameter:
            parameters = gf.Parameters(*list(parameters)[1:])

        if exclude:
            parameters = gf.Parameters(*[p for p in parameters if p.name not in exclude])

        return parameters

    def render_signature(self) -> BlockContent:
        """
        Render the signature of this callable
        """
        name = self.signature_name if self.show_signature_name else ""

        # Check for @overload variants
        overloads = getattr(self.obj, "overloads", None)
        if overloads:
            return self._render_overload_signatures(name, overloads)

        sig = formatted_signature(name, self.render_signature_parameters())
        return Div(
            CodeBlock(sig, Attr(classes=["python"])),
            Attr(classes=["doc-signature", f"doc-{self.obj.kind}"]),
        )

    def _render_overload_signatures(self, name: str, overloads: list) -> BlockContent:
        """Render multiple @overload signatures as a single code block."""
        sig_lines: list[str] = []
        for ov in overloads:
            if not hasattr(ov, "parameters"):
                continue
            params: list[str] = []
            for p in ov.parameters:
                ann = str(p.annotation) if p.annotation else ""
                default = str(p.default) if p.default else ""
                if ann and default:
                    params.append(f"{p.name}: {ann} = {default}")
                elif ann:
                    params.append(f"{p.name}: {ann}")
                elif default:
                    params.append(f"{p.name}={default}")
                else:
                    params.append(p.name)
            ret = str(ov.returns) if ov.returns else ""
            sig = f"{name}({', '.join(params)})"
            if ret:
                sig += f" -> {ret}"
            sig_lines.append(sig)

        if not sig_lines:
            sig_lines.append(f"{name}()")

        return Div(
            CodeBlock("\n".join(sig_lines), Attr(classes=["python"])),
            Attr(classes=["doc-signature", f"doc-{self.obj.kind}"]),
        )

    def render_signature_parameters(self) -> list[str]:
        """
        Render parameters in a function / method signature

        i.e. The stuff in the brackets of func(a, b, c=3, d=4, **kwargs)
        """
        params: list[str] = []
        prev, cur = 0, 1
        state: tuple[str, str] = (
            str(gf.ParameterKind.positional_or_keyword),
            str(gf.ParameterKind.positional_or_keyword),
        )

        for parameter in self.parameters:
            state = state[cur], str(parameter.kind)
            append_transition_token = state[prev] != state[cur] and state[prev] != str(
                gf.ParameterKind.var_positional
            )

            if append_transition_token:
                if state[prev] == str(gf.ParameterKind.positional_only):
                    params.append("/")
                if state[cur] == str(gf.ParameterKind.keyword_only):
                    params.append("*")

            params.append(self.render_signature_parameter(parameter))
        return params

    def render_signature_parameter(self, el: gf.Parameter) -> str:
        """
        Parameter for the function/method signature

        This is a single item in the brackets of

            func(a, b, c=3, d=4, **kwargs)
        """
        default = None
        if el.kind == gf.ParameterKind.var_keyword:
            name = f"**{el.name}"
        elif el.kind == gf.ParameterKind.var_positional:
            name = f"*{el.name}"
        else:
            name = el.name
            if el.default is not None:
                default = repr_obj(el.default)

        if self.show_signature_annotation and el.annotation is not None:
            annotation, equals = f": {el.annotation}", " = "
        else:
            annotation, equals = "", "="

        default = (default and f"{equals}{default}") or ""
        return f"{name}{annotation}{default}"


class RenderDocCallMixin(__RenderDocCallMixin):
    """
    Extend Rendering of objects that can be called
    """
