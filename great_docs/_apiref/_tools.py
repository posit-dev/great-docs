"""
Little functions that can be used in userland
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import griffe as gf

from ._render import get_render_type
from ._settings import Settings
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


def _render(obj: gf.Object | gf.Alias, settings: Settings | None = None) -> str:
    """
    Render an object's documentation as Quarto Markdown

    Parameters
    ----------
    obj
        The object to render.
    settings
        The API reference settings, or `None` to use the defaults.

    Returns
    -------
    :
        The object's documentation as Quarto Markdown.
    """
    node = griffe_to_doc(obj, inherited=False, skip_aliases=True)
    return str(get_render_type(node)(node, settings=settings or Settings()))


def render_code_variable(
    code: str, name: str | None = None, settings: Settings | None = None
) -> str:
    """
    Render a variable or module from source as Quarto Markdown

    Parameters
    ----------
    code
        The source of a module.
    name
        The name of the variable to render, or `None` to render the module.
    settings
        The API reference settings, or `None` to use the defaults.

    Returns
    -------
    :
        The variable's or module's documentation as Quarto Markdown.
    """
    with gf.temporary_visited_package(
        "package", {"__init__.py": code}, docstring_parser="numpy"
    ) as m:
        obj = m[name] if name else m
    return _render(obj, settings)


def render_type_object(path: str | type | MethodType, settings: Settings | None = None) -> str:
    """
    Render a Python object's documentation as Quarto Markdown

    Parameters
    ----------
    path
        The object, or its import path.
    settings
        The API reference settings, or `None` to use the defaults.

    Returns
    -------
    :
        The object's documentation as Quarto Markdown.
    """
    if not isinstance(path, str):
        path = _canonical_path(path)
    return _render(get_object(path), settings)
