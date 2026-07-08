"""
Little functions that can be used in userland
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import griffe as gf

from ._render import get_render_type
from ._type_checks import griffe_to_doc
from .introspect import get_object

if TYPE_CHECKING:
    from types import MethodType


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


def _render(obj: gf.Object | gf.Alias) -> str:
    """
    Render a `gf.Object` to qmd
    """
    node = griffe_to_doc(obj, inherited=False, skip_aliases=True)
    return str(get_render_type(node)(node))


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
