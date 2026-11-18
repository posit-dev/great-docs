"""
Signatures and definition sections of functions, methods and classes

A class takes its signature from its constructor, and a method's signature drops
`self` or `cls`. Both signature styles show parameter defaults, and each
`@overload` variant keeps its annotations.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs.pandoc.blocks import (
    BlockContent,
    Blocks,
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
from .objects import ObjectRenderer

if TYPE_CHECKING:
    from ..content import DocClass, DocFunction


class CallableRendererMixin(ObjectRenderer):
    """
    The signature and definition sections shared by functions, methods and classes

    A class takes its signature from its constructor. The signature leaves out
    `self` or `cls` and any excluded parameters. Ordinary signatures omit
    annotations, while `@overload` variants keep the annotations that tell them
    apart.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to a callable and record each parameter's kind"""
        super().__post_init__()

        self.doc = cast("DocFunction | DocClass", self.doc)  # pyright: ignore[reportUnnecessaryCast]
        self.obj = cast("gf.Function", self.obj)  # pyright: ignore[reportUnnecessaryCast]

        # Docstring parameter entries lack the parameter kind that rendering needs.
        self._parameter_kinds = {p.name: p.kind for p in self.parameters}

    def render_parameters_section(self, el: gf.DocstringSectionParameters) -> BlockContent:
        """
        Render a `Parameters` section

        Parameters
        ----------
        el
            The `Parameters` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_other_parameters_section(
        self, el: gf.DocstringSectionOtherParameters
    ) -> BlockContent:
        """
        Render an `Other Parameters` section

        Parameters
        ----------
        el
            The `Other Parameters` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_returns_section(self, el: gf.DocstringSectionReturns) -> BlockContent:
        """
        Render a `Returns` section

        Parameters
        ----------
        el
            The `Returns` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_yields_section(self, el: gf.DocstringSectionYields) -> BlockContent:
        """
        Render a `Yields` section

        Parameters
        ----------
        el
            The `Yields` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_receives_section(self, el: gf.DocstringSectionReceives) -> BlockContent:
        """
        Render a `Receives` section

        Parameters
        ----------
        el
            The `Receives` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_raises_section(self, el: gf.DocstringSectionRaises) -> BlockContent:
        """
        Render a `Raises` section

        Parameters
        ----------
        el
            The `Raises` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_warns_section(self, el: gf.DocstringSectionWarns) -> BlockContent:
        """
        Render a `Warns` section

        Parameters
        ----------
        el
            The `Warns` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_init_parameters_section(self, el: DCDocstringSectionInitParameters) -> BlockContent:
        """
        Render the `Init Parameters` section of a dataclass

        Parameters
        ----------
        el
            The `Init Parameters` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_parameter_attributes_section(
        self, el: DCDocstringSectionParameterAttributes
    ) -> BlockContent:
        """
        Render the `Parameter Attributes` section of a dataclass

        Parameters
        ----------
        el
            The `Parameter Attributes` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    def render_type_parameters_section(self, el: gf.DocstringSectionTypeParameters) -> BlockContent:
        """
        Render a `Type Parameters` section

        A generic class or function declares its type parameters as part of
        the signature this renderer builds.

        Parameters
        ----------
        el
            The `Type Parameters` section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """
        return self.render_definition_items(el)

    @cached_property
    def parameters(self) -> gf.Parameters:
        """
        The parameters that the signature shows

        The view leaves out excluded parameters and the `self` or `cls` of a method or
        constructor. The callable's original parameters stay available for matching
        docstring sections and selecting dataclass fields.
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
        """The callable's documented parameters, with its original parameters and exclusions"""
        return CallableDocumentation.make(self.obj)

    def render_description(self) -> BlockContent:
        """
        Render the subject, the Usage and source row, and the signature, in that order

        Returns
        -------
        :
            The parts that are not omitted.
        """
        return Blocks([self.render_docstring_subject(), self.render_usage_source(), self.signature])

    def render_signature(self) -> BlockContent:
        """
        Render the signature of this callable

        The `highlighted` style produces a `pythonsignature` code block, which
        Quarto colours with the build's signature grammar. The `plain` style
        produces inline markup, which a `code` element can hold but a `pre`
        block cannot. Callable names use `fu` in `highlighted` and `sig-name`
        in `plain`; parameters use `va` and `doc-parameter-name`, respectively.
        Literal colours apply only within the code block's `sourceCode` wrapper.

        Returns
        -------
        :
            The signature, one line per `@overload` variant when there are any.
        """
        name = self.signature_name
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
        :
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
        :
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
                """Format one overload parameter with its annotation and default"""
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
            if self._callable.excluded_names or (
                parameters and parameters[-1].kind == gf.ParameterKind.positional_only
            ):
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
        Render the signature's parameters with their `/` and `*` separators

        Override `render_signature_parameter` to change how each parameter renders; the
        separators stay in place.

        Returns
        -------
        :
            The rendered parameters in signature order, with the separators as items of
            their own.
        """
        return self._signature_parameters(self.parameters, self.render_signature_parameter)

    def _signature_parameters(
        self, parameters: gf.Parameters, render: Callable[[gf.Parameter], str]
    ) -> list[str]:
        """
        Place parameter-kind separators around the retained arguments

        A `/` also ends the list when its last parameter is positional-only and the
        callable has excluded parameters.

        Parameters
        ----------
        parameters
            The parameters that the signature shows.
        render
            The function that renders one parameter.

        Returns
        -------
        :
            The rendered parameters in order, with `/` after the last positional-only one
            and `*` before the first keyword-only one unless `*args` precedes it.
        """
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
        if parameters and parameters[-1].kind == gf.ParameterKind.positional_only:
            params.append("/")
        return params

    def render_signature_parameter(self, el: gf.Parameter) -> str:
        """
        Render one parameter of an ordinary signature, with its prefix and default

        Variadic parameters keep their `*` or `**` prefix, and string defaults use
        normalised quotes. Annotations are omitted; `@overload` variants render their
        own annotated parameters. Override this method to change each parameter's text.

        Parameters
        ----------
        el
            The parameter.

        Returns
        -------
        :
            The parameter's text in the signature.
        """
        if el.kind == gf.ParameterKind.var_keyword:
            return f"**{el.name}"
        if el.kind == gf.ParameterKind.var_positional:
            return f"*{el.name}"
        default = "" if el.default is None else repr_obj(el.default)
        return f"{el.name}={default}" if default else el.name
