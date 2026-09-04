from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs.pandoc.blocks import (
    BlockContent,
)
from great_docs.pandoc.components import Attr

from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .._format import repr_obj
from .._signature import make_call_signature_text, render_signature_block
from .._type_checks import is_enum, is_typeddict
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

        The `highlighted` style writes a fenced code block, which Quarto
        highlights and `post-render.py` then re-highlights. The `plain` style
        writes inline markup instead, which a `code` element can hold but a
        `pre` block cannot. The callable's name carries `sig-name` in both,
        but parameters differ: `plain` uses `doc-parameter-name`, whilst
        `highlighted` uses Pygments' `va` token. The stylesheet's colours for
        the literal classes are scoped to Quarto's own `sourceCode` wrapper,
        so today they reach only the code block.
        """
        name = self.signature_name if self.show_signature_name else ""
        attr = Attr(classes=["doc-signature", f"doc-{self.obj.kind}"])
        return render_signature_block(self._signature_lines(name), attr)

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
        overloads = self._overloads()
        if overloads:
            return self._overload_signature_lines(name, overloads)

        # TypedDicts are structural type definitions, not constructors, and enums
        # are reached through their members rather than called, so neither ever
        # shows an empty `()`.
        if is_typeddict(self.obj) or is_enum(self.obj):
            return [(name, [])]

        params = self.render_signature_parameters()
        return [(make_call_signature_text(name, params), params)]

    def _overloads(self) -> list[gf.Function]:
        """
        The `@overload` variants of this callable

        For functions, `.overloads` is a `list[Function]`. For classes it is a
        `dict[str, list[Function]]` keyed by member name, which is non-empty
        (and thus truthy) for any class that merely defines methods, even when
        none of them are actually overloaded. Flattening it makes the result
        reflect real overloads, so dataclass constructor signatures are not
        lost.

        Returns
        -------
        The overload variants, empty when the callable has none.
        """
        overloads = getattr(self.obj, "overloads", []) or []
        if isinstance(overloads, dict):
            return [ov for ovs in overloads.values() for ov in ovs]
        return list(overloads)

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
        annotation, and the parameters it was built from.
        """
        lines: list[tuple[str, list[str]]] = []
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
            text = make_call_signature_text(name, params)
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
