from __future__ import annotations

import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from typing import NamedTuple, cast

import griffe as gf


class Constructor(NamedTuple):
    """
    The callable behind a class's signature
    """

    name: str
    """`__init__` or `__new__`"""

    parameters: gf.Parameters
    """The parameters, including `self` or `cls`"""

    overloads: list[gf.Function]
    """The `@overload` variants, empty when there are none"""


def class_constructor(cls: gf.Class | gf.Alias) -> Constructor:
    """
    Find the constructor that a class's signature shows

    Griffe takes a class's parameters from `__init__` alone. Extension classes
    (PyO3, pybind11, Cython) declare their constructor in `__new__` instead,
    and their stubs often pair it with an `__init__` that takes only `self`.
    The constructor is `__init__` when it, or one of its overloads, takes
    arguments beyond `self` and `*args`/`**kwargs`, then `__new__` under the
    same test, and otherwise `__init__`.

    Parameters
    ----------
    cls
        The class.

    Returns
    -------
    :
        The constructor.
    """
    try:
        members = cls.all_members
    except (gf.AliasResolutionError, gf.CyclicAliasError):
        members = cls.members
    # Overloads without an implementation, as in stubs, stay on the class.
    class_overloads: dict[str, list[gf.Function]] = getattr(cls, "overloads", None) or {}

    candidates: list[Constructor] = []
    for name in ("__init__", "__new__"):
        member = members.get(name)
        try:
            is_function = member is not None and member.is_function
        except (gf.AliasResolutionError, gf.CyclicAliasError):
            is_function = False
        func = cast("gf.Function", member) if is_function else None
        parameters = func.parameters if func else gf.Parameters()
        own_overloads = func.overloads if func else None
        overloads = list(own_overloads or class_overloads.get(name) or [])
        candidates.append(Constructor(name, parameters, overloads))

    for candidate in candidates:
        if takes_arguments(candidate.parameters) or any(
            takes_arguments(ov.parameters) for ov in candidate.overloads
        ):
            return candidate
    return candidates[0]


def without_receiver(parameters: gf.Parameters) -> gf.Parameters:
    """
    Drop a leading `self` or `cls` from a constructor's parameters
    """
    params = list(parameters)
    if params and params[0].name in ("self", "cls"):
        return gf.Parameters(*params[1:])
    return parameters


def takes_arguments(parameters: gf.Parameters) -> bool:
    """
    Whether a constructor names any argument beyond `self` or `cls`

    A bare `*args` or `**kwargs` does not count, as it only passes the
    arguments on.
    """
    variadic = (gf.ParameterKind.var_positional, gf.ParameterKind.var_keyword)
    return any(p.kind not in variadic for p in without_receiver(parameters))


def parse_class_docstring(cls: gf.Class | gf.Alias) -> None:
    """
    Parse a class docstring against the parameters of its `__new__`

    Griffe checks the `Parameters` section of a class docstring against
    `__init__`. When the class signature comes from `__new__`, griffe warns
    that each documented parameter is missing from the signature and leaves
    its annotation and default unset. This parses the docstring with those
    warnings held back and fills each parameter in from `__new__`. The parsed
    sections are cached on the docstring, so later reads see the filled-in
    parameters. Other classes are left for griffe to parse as usual.

    Parameters
    ----------
    cls
        A class with a docstring.
    """
    docstring = cls.docstring
    if docstring is None:
        return
    constructor = class_constructor(cls)
    if constructor.name != "__new__":
        return
    signature = {p.name: p for p in without_receiver(constructor.parameters)}

    with _without_parameter_warnings(signature):
        sections = docstring.parsed

    for section in sections:
        if not isinstance(section, gf.DocstringSectionParameters):
            continue
        for item in section.value:
            param = signature.get(item.name.lstrip("*"))
            if param is None:
                continue
            if item.annotation is None:
                item.annotation = param.annotation
            if item.value is None:
                item.value = param.default


# Griffe's warnings about the parameters of a `Parameters` section, by parser.
# Each names the parameters it concerns.
_MISSING_WARNING = re.compile(
    r"Parameter '(?P<names>[^']+)' does not appear in the function signature"  # all
    r"|No matching parameter for '(?P<sphinx>[^']+)'"  # Sphinx
)
_UNTYPED_WARNING = re.compile(
    r"No type or annotation for parameter '(?P<names>[^']+)'"  # Google
    r"|No types or annotations for parameters \[(?P<numpy>[^\]]*)\]"  # NumPy
)


@contextmanager
def _without_parameter_warnings(signature: dict[str, gf.Parameter]) -> Generator[None]:
    """
    Hold back griffe's warnings about parameters that the signature resolves

    A missing-parameter warning is held back for parameters in the
    signature, a missing-type warning for parameters it annotates.
    """

    def names(match: re.Match[str]) -> list[str]:
        text = next(group for group in match.groups() if group is not None)
        found = re.findall(r"'([^']+)'", text) or [text]
        return [name.strip().lstrip("*") for name in found]

    def keep(record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if missing := _MISSING_WARNING.search(message):
            return not all(name in signature for name in names(missing))
        if untyped := _UNTYPED_WARNING.search(message):
            return not all(
                name in signature and signature[name].annotation is not None
                for name in names(untyped)
            )
        return True

    # Griffe's docstring parsers log through the `griffe` logger.
    logger = logging.getLogger("griffe")
    logger.addFilter(keep)
    try:
        yield
    finally:
        logger.removeFilter(keep)
