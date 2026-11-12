from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs.pandoc.blocks import (
    BlockContent,
)
from great_docs.pandoc.components import Attr

from .._constructor import without_receiver
from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .._format import repr_obj
from .._parameter_docs import CallableDocumentation
from .._signature import make_call_signature_text, render_signature_block
from .._type_checks import is_enum, is_typeddict
from .doc import RenderDoc

if TYPE_CHECKING:
    from ..content import DocClass, DocFunction


class __RenderDocCallMixin(RenderDoc):
    """
    Mixin to render Doc objects that can be called

    i.e. classes (for the __init__ or __new__ method) and functions/methods
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
        obj = self.obj
        if obj.is_class:
            return without_receiver(self._callable.parameters)

        parameters = self._callable.parameters

        if not len(parameters) > 0 or not obj.parent:
            return parameters

        param = self._callable.original_parameters[0].name
        omit_first_parameter = (
            obj.parent.is_class
            and param in ("self", "cls")
            and ("staticmethod" not in obj.labels or not self._callable.excluded_names)
        )

        if omit_first_parameter:
            parameters = gf.Parameters(*list(parameters)[1:])

        return parameters

    @cached_property
    def _callable(self) -> CallableDocumentation:
        """
        Build the callable's documented parameter view
        """
        return CallableDocumentation.make(self.obj)

    def render_signature(self) -> BlockContent:
        """
        Render the signature of this callable

        The `highlighted` style produces a `pythonsignature` code block, which
        Quarto colours with the build's signature grammar. The `plain` style
        produces inline markup, which a `code` element can hold but a `pre`
        block cannot. Callable names use `fu` in `highlighted` and `sig-name`
        in `plain`; parameters use `va` and `doc-parameter-name`, respectively.
        Literal colours apply only within the code block's `sourceCode` wrapper.
        """
        name = self.signature_name if self.show_signature_name else ""
        attr = Attr(classes=["doc-signature", f"doc-{self.kind_slug}"])
        style = self.settings.callable_signatures.style
        return render_signature_block(self._signature_lines(name), attr, style)

    def _signature_lines(self, name: str) -> list[tuple[str, list[str]]]:
        """
        Build the lines of the signature, each with the parameters behind it

        A callable has one line and an overloaded one a line per `@overload`
        variant. Each line keeps the parameters it was built from, so that a
        style which marks up parameters individually can find them where
        they stand.

        Parameters
        ----------
        name
            Name of the callable, or the empty string when the signature
            does not show one.

        Returns
        -------
        One pair per line: the line's text, and the parameters it was
        built from.
        """
        overloads = self._callable.overloads
        if overloads:
            return self._overload_signature_lines(name, overloads)

        # TypedDicts are structural type definitions, not constructors, and enums
        # are reached through their members rather than called, so neither ever
        # shows an empty `()`.
        if is_typeddict(self.obj) or is_enum(self.obj):
            return [(name, [])]

        params = self.render_signature_parameters()
        wrap = self.settings.callable_signatures.wrap
        return [(make_call_signature_text(name, params, wrap), params)]

    def _overload_signature_lines(
        self, name: str, overloads: list[gf.Function]
    ) -> list[tuple[str, list[str]]]:
        """
        Build one signature line per `@overload` variant

        Parameters
        ----------
        name
            Name of the callable.
        overloads
            The overload variants of the callable.

        Returns
        -------
        One pair per variant: the variant's text, including its return
        annotation, and the parameters it was built from. A class's
        variants drop `self` or `cls` and the return annotation, as
        calling the class returns an instance.
        """
        is_class = self.obj.is_class
        is_method = (
            self.obj.parent is not None
            and self.obj.parent.is_class
            and "staticmethod" not in self.obj.labels
        )
        lines: list[tuple[str, list[str]]] = []
        for ov in overloads:
            if not hasattr(ov, "parameters"):
                continue

            def render_parameter(p: gf.Parameter) -> str:
                ann = repr_obj(p.annotation) if p.annotation else ""
                default = repr_obj(p.default) if p.default else ""
                name = p.name
                if self._callable.excluded_names:
                    if p.kind == gf.ParameterKind.var_positional:
                        name = f"*{name}"
                    elif p.kind == gf.ParameterKind.var_keyword:
                        name = f"**{name}"
                if ann and default:
                    return f"{name}: {ann} = {default}"
                elif ann:
                    return f"{name}: {ann}"
                elif default:
                    return f"{name}={default}"
                else:
                    return name

            parameters = (
                without_receiver(ov.parameters)
                if is_class or (self._callable.excluded_names and is_method)
                else ov.parameters
            )
            if self._callable.excluded_names:
                params = self._signature_parameters(parameters, render_parameter)
            else:
                params = [render_parameter(p) for p in parameters]
            ret = repr_obj(ov.returns) if ov.returns and not is_class else ""
            text = make_call_signature_text(name, params, self.settings.callable_signatures.wrap)
            if ret:
                text += f" -> {ret}"
            lines.append((text, params))

        if not lines:
            lines.append((f"{name}()", []))
        return lines

    def render_signature_parameters(self) -> list[str]:
        """
        Render parameters in a function / method signature

        i.e. The stuff in the brackets of func(a, b, c=3, d=4, **kwargs)
        """
        return self._signature_parameters(self.parameters, self.render_signature_parameter)

    def _signature_parameters(
        self, parameters: gf.Parameters, render: Callable[[gf.Parameter], str]
    ) -> list[str]:
        """Place parameter-kind separators around the retained arguments"""
        params: list[str] = []
        prev, cur = 0, 1
        state: tuple[str, str] = (
            str(gf.ParameterKind.positional_or_keyword),
            str(gf.ParameterKind.positional_or_keyword),
        )

        for parameter in parameters:
            state = state[cur], str(parameter.kind)
            append_transition_token = state[prev] != state[cur] and state[prev] != str(
                gf.ParameterKind.var_positional
            )

            if append_transition_token:
                if state[prev] == str(gf.ParameterKind.positional_only):
                    params.append("/")
                if state[cur] == str(gf.ParameterKind.keyword_only):
                    params.append("*")

            params.append(render(parameter))
        if (
            parameters
            and parameters[-1].kind == gf.ParameterKind.positional_only
            and self._callable.excluded_names
        ):
            params.append("/")
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
            annotation, equals = f": {repr_obj(el.annotation)}", " = "
        else:
            annotation, equals = "", "="

        default = (default and f"{equals}{default}") or ""
        return f"{name}{annotation}{default}"


class RenderDocCallMixin(__RenderDocCallMixin):
    """
    Extension point for the rendering of objects that can be called
    """
