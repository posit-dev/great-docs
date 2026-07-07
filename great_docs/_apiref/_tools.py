"""
Little functions that can be used in userland
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import griffe as gf

from . import (
    RenderDocAttribute,
    RenderDocClass,
    RenderDocFunction,
    RenderDocModule,
)
from .content import Doc, DocAttribute, DocClass, DocFunction, DocModule
from .introspect import get_object

if TYPE_CHECKING:
    from types import MethodType

    from .typing import DocType


__all__ = (
    "render_code_variable",
    "render_type_object",
)


def _canonical_path(klass: type | MethodType) -> str:
    """
    Return the canonical path to a python type object
    """
    if not isinstance(klass, type):
        klass = klass.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__
    return f"{module}.{klass.__qualname__}"


def _render(obj: gf.Object) -> str:
    """
    Render a `gf.Object` to qmd
    """

    def to_doc(obj: gf.Object) -> "DocType":
        members = [
            to_doc(m)
            for m in obj.members.values()
            # imported variables are of type gf.Alias and we are
            # not interested in dealing with them.
            if not isinstance(m, gf.Alias)
        ]
        return Doc.from_griffe(obj.name, obj, members=members)  # pyright: ignore[reportUnknownMemberType]

    match node := to_doc(obj):
        case DocAttribute():
            _Render = RenderDocAttribute
        case DocClass():
            _Render = RenderDocClass
        case DocFunction():
            _Render = RenderDocFunction
        case DocModule():
            _Render = RenderDocModule

    return str(_Render(node))


def render_code_variable(code: str, name: str | None = None) -> str:
    """
    Render a named variable in code to qmd

    If name is None, render the code as a module
    """
    with gf.temporary_visited_package(
        "package", {"__init__.py": code}, docstring_parser="numpy"
    ) as m:
        obj = m[name] if name else m
    return _render(obj)


def render_type_object(path: str | type | MethodType) -> str:
    """
    Render a python object to qmd
    """
    if not isinstance(path, str):
        path = _canonical_path(path)
    return _render(get_object(path))
