"""
Text export of an API reference's prepared Python documentation

The export lists the reference's objects and selected members, and formats their docstring
sections with the built-in renderers. It keeps the docstring edits and exclusions of object
and docstring hooks.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import griffe as gf

from ._constructor import without_receiver
from ._parameter_docs import CallableDocumentation
from ._rendering._renderers import Renderers
from ._rendering._type_parameters import render_type_parameters
from ._type_checks import is_enum, is_typeddict
from .content import Doc, DocClass, DocModule, Page

if TYPE_CHECKING:
    from ._settings import Settings
    from .api_reference import APIReference


def summary(obj: gf.Object | gf.Alias) -> str:
    """
    Read the first line of an object's prepared docstring, without its trailing period

    Parameters
    ----------
    obj
        A prepared object.

    Returns
    -------
    :
        The first line of the docstring's leading text section, or an empty string when
        there is no docstring or it does not start with text.
    """
    if obj.docstring is None or not obj.docstring.parsed:
        return ""
    first = obj.docstring.parsed[0]
    if not isinstance(first, gf.DocstringSectionText):
        return ""
    lines = first.value.strip().splitlines()
    return lines[0].strip().rstrip(".") if lines else ""


def reference_text(reference: APIReference) -> str:
    """
    Format a reference's prepared objects as text

    Format each object's own sections with the built-in renderers. List each selected
    member separately, so the export keeps its documentation even when a renderer hides
    it on the page.

    Parameters
    ----------
    reference
        The reference whose resolved sections to format.

    Returns
    -------
    :
        Each reference section's heading and description, followed by the text of
        its objects.
    """
    lines: list[str] = []
    for section in reference.resolved:
        title = section.title or section.subtitle
        if title:
            lines.extend([f"\n## {title}\n", f"{section.desc}\n" if section.desc else "", ""])
        for entry in section.contents:
            for doc in _documents(entry):
                lines.extend([object_text(doc, reference.settings), ""])
    return "\n".join(lines)


def _documents(entry: object) -> Iterator[Doc]:
    """
    Yield the documented objects in an entry, each followed by its members

    Parameters
    ----------
    entry
        A resolved page or object.

    Yields
    ------
    :
        Each object once, without duplicating member pages.
    """
    if isinstance(entry, Page):
        for doc in entry.contents:
            yield from _documents(doc)
    elif isinstance(entry, Doc):
        yield entry
        if isinstance(entry, (DocClass, DocModule)):
            for member in entry.members:
                yield from _documents(member)


def object_text(doc: Doc, settings: Settings) -> str:
    """
    Format a prepared object's signatures and own documentation sections

    Keep defaults, annotations, overloads and constructor exclusions from the
    prepared model. Render recognised sections with the built-in renderers.
    Constructor descriptions follow selected membership; an undocumented class
    does not gain the body of an unselected constructor.
    """
    node = Doc.from_griffe(doc.name, doc.obj)
    renderer = Renderers().make(node, settings=settings)
    body = renderer.render_docstring_body()
    parts = [signature_text(doc.obj), renderer.docstring_subject, str(body) if body else None]
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def signature_text(obj: gf.Object | gf.Alias) -> str:
    """
    Format an object's signatures or declaration as text

    Keep parameter kinds, annotations, defaults and every overload. A class's signature is
    its selected constructor's, without the receiver or return annotation. An enum or a
    `TypedDict` shows only its name. Type parameter lists keep their bounds, constraints
    and defaults, and a PEP 695 alias shows its `type` declaration and value.

    Parameters
    ----------
    obj
        A prepared object.

    Returns
    -------
    :
        One signature per line for a function or class, the declaration of an attribute
        or type alias, the qualified name of a module, or the name of any other object.
    """
    name = obj.path if obj.is_module else obj.name
    if obj.is_type_alias:
        alias = cast("gf.TypeAlias", obj)
        declared = f"type {name}{render_type_parameters(alias.type_parameters)}"
        return f"{declared} = {alias.value}" if alias.value is not None else declared
    if obj.is_function or obj.is_class:
        if is_enum(obj) or is_typeddict(obj):
            return name
        facts = CallableDocumentation.make(obj)
        name += render_type_parameters(obj.type_parameters)
        signatures: list[str] = []
        variants = facts.overloads
        parameters = [variant.parameters for variant in variants] or [facts.parameters]
        for index, params in enumerate(parameters):
            if obj.is_class:
                params = without_receiver(params)
            returns = variants[index].returns if variants else getattr(obj, "returns", None)
            signature = _signature(params, None if obj.is_class else returns)
            signatures.append(f"{name}{signature}")
        return "\n".join(signatures)
    if obj.is_attribute:
        annotation = getattr(obj, "annotation", None)
        value = getattr(obj, "value", None)
        if annotation is not None:
            name += f": {annotation}"
        if value is not None:
            name += f" = {value}"
    return name


@dataclass(frozen=True, repr=False)
class _SignatureExpression:
    """A source expression whose representation retains its spelling"""

    text: str
    """The source spelling of an annotation or default value"""

    def __repr__(self) -> str:
        """Return the expression without adding string-literal quotes"""
        return self.text


_PARAMETER_KINDS = {
    gf.ParameterKind.positional_only: inspect.Parameter.POSITIONAL_ONLY,
    gf.ParameterKind.positional_or_keyword: inspect.Parameter.POSITIONAL_OR_KEYWORD,
    gf.ParameterKind.var_positional: inspect.Parameter.VAR_POSITIONAL,
    gf.ParameterKind.keyword_only: inspect.Parameter.KEYWORD_ONLY,
    gf.ParameterKind.var_keyword: inspect.Parameter.VAR_KEYWORD,
}


def _signature(parameters: gf.Parameters, returns: str | gf.Expr | None) -> inspect.Signature:
    """
    Build a Python signature that shows annotations and defaults as written

    Parameters
    ----------
    parameters
        The parameters, in order.
    returns
        The return annotation, or `None` to omit it.

    Returns
    -------
    :
        The signature. Variadic parameters have no default.
    """
    converted: list[inspect.Parameter] = []
    variadic = (gf.ParameterKind.var_positional, gf.ParameterKind.var_keyword)
    for parameter in parameters:
        default = (
            _SignatureExpression(str(parameter.default))
            if parameter.default is not None and parameter.kind not in variadic
            else inspect.Parameter.empty
        )
        annotation = (
            _SignatureExpression(str(parameter.annotation))
            if parameter.annotation is not None
            else inspect.Parameter.empty
        )
        converted.append(
            inspect.Parameter(
                parameter.name,
                _PARAMETER_KINDS[parameter.kind or gf.ParameterKind.positional_or_keyword],
                default=default,
                annotation=annotation,
            )
        )
    return inspect.Signature(
        converted,
        return_annotation=(
            _SignatureExpression(str(returns)) if returns is not None else inspect.Signature.empty
        ),
    )
