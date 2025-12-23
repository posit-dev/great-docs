"""
Little functions that can be used in userland
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import griffe as gf
import quartodoc.layout as layout
from quartodoc import get_object

from . import (
    RenderDocAttribute,
    RenderDocClass,
    RenderDocFunction,
    RenderDocModule,
    Renderer,
)

if TYPE_CHECKING:
    from types import MethodType

    from .typing import DocType


__all__ = (
    "render_code_variable",
    "render_type_object",
)


def _canonical_path(klass: type | MethodType) -> str:
    """
    Return the canonical path to python type object
    """
    if not isinstance(klass, type):
        klass = klass.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__
    return f"{module}.{klass.__qualname__}"


def _render(obj: gf.Object):
    """
    Render gf.Object to qmd
    """

    def toDocObject(obj: gf.Object) -> "DocType":
        members = [
            toDocObject(m)
            for m in obj.members.values()
            # imported variables are of type gf.Alias and we are
            # not interested in dealing with them.
            if not isinstance(m, gf.Alias)
        ]
        return layout.Doc.from_griffe(obj.name, obj, members=members)  # pyright: ignore[reportUnknownMemberType]

    match layout_obj := toDocObject(obj):
        case layout.DocAttribute():
            _Render = RenderDocAttribute
        case layout.DocClass():
            _Render = RenderDocClass
        case layout.DocFunction():
            _Render = RenderDocFunction
        case layout.DocModule():
            _Render = RenderDocModule

    return str(_Render(layout_obj, Renderer()))


def render_code_variable(code: str, name: str | None = None) -> str:
    """
    Render named variable in code to qmd

    If name is None, return code rendered as a module
    """
    with gf.temporary_visited_package(
        "package", {"__init__.py": code}, docstring_parser="numpy"
    ) as m:
        obj = m[name] if name else m
    return _render(obj)


def render_type_object(path: str | type | MethodType) -> str:
    """
    Render python object to qmd

    If name is None, return code rendered as a module
    """
    if not isinstance(path, str):
        path = _canonical_path(path)
    return _render(get_object(path))
