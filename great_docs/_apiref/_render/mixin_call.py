from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs.pandoc.blocks import (
    BlockContent,
    CodeBlock,
    Div,
)
from great_docs.pandoc.components import Attr

from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .._format import make_call_signature_text, repr_obj
from .doc import RenderDoc

if TYPE_CHECKING:
    from ..content import DocClass, DocFunction


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

    def render_parameters_section(self, el: gf.DocstringSectionParameters) -> BlockContent:
        """Render a `Parameters` section"""
        return self.render_definition_items(el)

    def render_other_parameters_section(
        self, el: gf.DocstringSectionOtherParameters
    ) -> BlockContent:
        """Render an `Other Parameters` section"""
        return self.render_definition_items(el)

    def render_returns_section(self, el: gf.DocstringSectionReturns) -> BlockContent:
        """Render a `Returns` section"""
        return self.render_definition_items(el)

    def render_yields_section(self, el: gf.DocstringSectionYields) -> BlockContent:
        """Render a `Yields` section"""
        return self.render_definition_items(el)

    def render_receives_section(self, el: gf.DocstringSectionReceives) -> BlockContent:
        """Render a `Receives` section"""
        return self.render_definition_items(el)

    def render_raises_section(self, el: gf.DocstringSectionRaises) -> BlockContent:
        """Render a `Raises` section"""
        return self.render_definition_items(el)

    def render_warns_section(self, el: gf.DocstringSectionWarns) -> BlockContent:
        """Render a `Warns` section"""
        return self.render_definition_items(el)

    def render_init_parameters_section(self, el: DCDocstringSectionInitParameters) -> BlockContent:
        """Render the `Init Parameters` section of a dataclass"""
        return self.render_definition_items(el)

    def render_parameter_attributes_section(
        self, el: DCDocstringSectionParameterAttributes
    ) -> BlockContent:
        """Render the `Parameter Attributes` section of a dataclass"""
        return self.render_definition_items(el)

    def render_type_parameters_section(self, el: gf.DocstringSectionTypeParameters) -> BlockContent:
        """
        Render a `Type Parameters` section

        A generic class or function declares its type parameters as part of
        the signature this renderer builds.
        """
        return self.render_definition_items(el)

    @cached_property
    def parameters(self) -> gf.Parameters:
        """
        The parameters of the callable
        """
        from .._globals import EXCLUSIONS

        obj = self.obj
        parameters = obj.parameters

        exclude = EXCLUSIONS.parameters.get(self.obj.path, ())
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

        # Check for @overload variants.
        # For functions, `.overloads` is a `list[Function]`. For classes it is a
        # `dict[str, list[Function]]` keyed by member name, which is non-empty
        # (and thus truthy) for any class that merely defines methods, even when
        # none of them are actually overloaded. Flatten it so the check reflects
        # real overloads and dataclass constructor signatures are not lost.
        overloads_raw = getattr(self.obj, "overloads", []) or []
        if isinstance(overloads_raw, dict):
            overloads: list[gf.Function] = [ov for ovs in overloads_raw.values() for ov in ovs]
        else:
            overloads = list(overloads_raw)
        if overloads:
            return self._render_overload_signatures(name, overloads)

        sig = make_call_signature_text(name, self.render_signature_parameters())
        return Div(
            CodeBlock(sig, Attr(classes=["python"])),
            Attr(classes=["doc-signature", f"doc-{self.obj.kind}"]),
        )

    def _render_overload_signatures(self, name: str, overloads: list[gf.Function]) -> BlockContent:
        """Render multiple `@overload` signatures as a single code block"""
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
            sig = make_call_signature_text(name, params)
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
        Render a parameter for the function/method signature

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
    Extension point for the rendering of objects that can be called
    """
