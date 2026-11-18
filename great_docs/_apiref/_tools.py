"""
Rendering of Python objects and source snippets as Quarto Markdown

Each call prepares and renders its object with a new extension that holds only the
handlers registered through `great_docs.hooks`, and closes it before returning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import griffe as gf

from ._conversion import griffe_to_doc
from ._customisation import Extension
from ._settings import Settings
from .introspect import get_object, get_parser_defaults

if TYPE_CHECKING:
    from types import MethodType

    from griffe import DocstringOptions


__all__ = (
    "render_code_variable",
    "render_type_object",
)


def _canonical_path(klass: type | MethodType) -> str:
    """
    Return the canonical import path of a Python type object

    Parameters
    ----------
    klass
        The type, or an object whose type to use.

    Returns
    -------
    :
        The dotted path, without the module for built-in types.
    """
    if not isinstance(klass, type):
        klass = klass.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__
    return f"{module}.{klass.__qualname__}"


def _render(obj: gf.Object | gf.Alias, settings: Settings | None = None) -> str:
    """
    Prepare and render one object's documentation as Quarto Markdown

    Parameters
    ----------
    obj
        The object or alias to document.
    settings
        Parsing and rendering settings, or `None` for defaults.

    Returns
    -------
    :
        The object's documentation, or an empty string when an object hook excludes it.
    """
    settings = settings or Settings()
    extension = Extension(settings)
    try:
        extension.load()
        node = griffe_to_doc(obj, inherited=False, skip_aliases=True, prepare=extension.prepare)
        if node is None:
            return ""
        with extension.error_context("render", obj.path):
            return str(extension.renderers.make(node, extension=extension))
    finally:
        extension.close()


def render_code_variable(
    code: str,
    name: str | None = None,
    settings: Settings | None = None,
) -> str:
    """
    Render a variable or module from source as Quarto Markdown

    Parameters
    ----------
    code
        The source of a temporary module. Each call documents its own module, even when
        snippets reuse names.
    name
        The variable name, or `None` to render the module.
    settings
        Parsing and rendering settings, or `None` for defaults. The snippet is parsed
        with their parser and its default options.

    Returns
    -------
    :
        The documentation, or an empty string when an object hook excludes the object.
    """
    settings = settings or Settings()
    defaults = get_parser_defaults(settings.parser)
    options = cast("DocstringOptions", defaults) if defaults else None
    with gf.temporary_visited_package(
        "package",
        {"__init__.py": code},
        docstring_parser=gf.Parser(settings.parser),
        docstring_options=options,
    ) as module:
        obj = module[name] if name else module
    return _render(obj, settings)


def render_type_object(path: str | type | MethodType, settings: Settings | None = None) -> str:
    """
    Render a Python object's documentation as Quarto Markdown

    Parameters
    ----------
    path
        The object or its qualified import path.
    settings
        Parsing, loading and rendering settings, or `None` for defaults.

    Returns
    -------
    :
        The documentation, or an empty string when an object hook excludes the object.
    """
    settings = settings or Settings()
    if not isinstance(path, str):
        path = _canonical_path(path)
    obj = get_object(path, parser=settings.parser, dynamic=settings.dynamic or False)
    return _render(obj, settings)
