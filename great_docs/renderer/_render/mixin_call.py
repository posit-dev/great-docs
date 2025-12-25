from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, TypeAlias, cast

import griffe as gf
from quartodoc.pandoc.blocks import (
    BlockContent,
    CodeBlock,
    DefinitionItem,
    DefinitionList,
    Div,
)
from quartodoc.pandoc.components import Attr
from quartodoc.pandoc.inlines import Code

from .._format import formatted_signature, repr_obj
from .._griffe.docstrings import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .doc import RenderDoc

if TYPE_CHECKING:
    from quartodoc.layout import DocClass, DocFunction

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

    @RenderDoc.render_section.register  # pyright: ignore[reportFunctionMemberAccess]
    def _(self, el: DocstringSectionWithDefinitions):
        """
        Render docstring sections that have a list of definitions

        e.g. Parameters, Other Parameters, Returns, Yields, Receives,
             Warns, Attributes
        """

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
            return Code(str(term)).html, el.description

        items = [render_section_item(item) for item in el.value]
        return Div(
            DefinitionList(items),
            Attr(classes=["doc-definition-items"]),
        )

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
        # For now, we do not do any interlinking in the signature
        name = self.signature_name if self.show_signature_name else ""
        sig = formatted_signature(name, self.render_signature_parameters())
        return Div(
            CodeBlock(sig, Attr(classes=["python"])),
            Attr(classes=["doc-signature", f"doc-{self.kind}"]),
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
            annotation, equals = f" : {el.annotation}", " = "
        else:
            annotation, equals = "", "="

        default = (default and f"{equals}{default}") or ""
        return f"{name}{annotation}{default}"


class RenderDocCallMixin(__RenderDocCallMixin):
    """
    Extend Rendering of objects that can be called
    """
