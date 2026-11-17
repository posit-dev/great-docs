"""
Rendering of Python objects and source snippets as Quarto Markdown

Helpers may share an active reference's acquisition, prepared documentation and
renderer choices. Standalone calls own and close fresh preparation state.
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

    from .api_reference import APIReference


__all__ = (
    "render_code_variable",
    "render_type_object",
)


def _canonical_path(klass: type | MethodType) -> str:
    """Return the canonical import path of a Python type object"""
    if not isinstance(klass, type):
        klass = klass.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__
    return f"{module}.{klass.__qualname__}"


def _render_settings(settings: Settings | None, reference: APIReference | None) -> Settings:
    """Select operation settings and reject conflicting helper settings"""
    if reference is None:
        return settings or Settings()
    if settings is not None and settings != reference.settings:
        raise ValueError("Helper settings conflict with the active API reference settings.")
    return reference.settings


def _render(
    obj: gf.Object | gf.Alias,
    settings: Settings | None = None,
    *,
    customisation: APIReference | None = None,
) -> str:
    """
    Prepare and render one object's documentation as Quarto Markdown

    Parameters
    ----------
    obj
        The object or alias to document.
    settings
        Settings for a standalone call. With `customisation`, omit these or
        supply settings equal to the active reference's settings.
    customisation
        An active reference whose semantic preparation and renderer choices to
        reuse. The caller retains ownership of its lifetime.

    Returns
    -------
    :
        The object's documentation, or an empty string when an object hook excludes it.
    """
    reference = customisation
    selected_settings = _render_settings(settings, reference)
    extension = reference.extension if reference is not None else Extension(selected_settings)
    try:
        extension.load()
        prepare = reference.prepare if reference is not None else extension.prepare
        node = griffe_to_doc(obj, inherited=False, skip_aliases=True, prepare=prepare)
        if node is None:
            return ""
        with extension.error_context("render", obj.path):
            return str(extension.renderers.make(node, settings=selected_settings))
    finally:
        if reference is None:
            extension.close()


def render_code_variable(
    code: str,
    name: str | None = None,
    settings: Settings | None = None,
    *,
    customisation: APIReference | None = None,
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
        Standalone semantic and rendering settings. The parser and its registered
        defaults apply to the snippet. `None` uses default settings.
    customisation
        An active API reference to reuse for preparation and renderer choices.
        Omit `settings` to use the reference's settings; conflicting values raise.
        This helper leaves the reference open.

    Returns
    -------
    :
        The documentation, or an empty string when an object hook excludes the object.
    """
    reference = customisation
    selected_settings = _render_settings(settings, reference)
    defaults = get_parser_defaults(selected_settings.parser)
    options = cast("DocstringOptions", defaults) if defaults else None
    with gf.temporary_visited_package(
        "package",
        {"__init__.py": code},
        docstring_parser=gf.Parser(selected_settings.parser),
        docstring_options=options,
    ) as module:
        obj = module[name] if name else module
    return _render(obj, selected_settings, customisation=reference)


def render_type_object(
    path: str | type | MethodType,
    settings: Settings | None = None,
    *,
    customisation: APIReference | None = None,
) -> str:
    """
    Render a Python object's documentation as Quarto Markdown

    Parameters
    ----------
    path
        The object or its qualified import path.
    settings
        Standalone semantic and rendering settings, or `None` for defaults.
    customisation
        An active reference whose loader, parser, prepared facts and renderer
        choices to reuse. Omit `settings` to use the reference's settings;
        conflicting values raise. This helper leaves the reference open.

    Returns
    -------
    :
        The documentation, or an empty string when an object hook excludes the object.
    """
    reference = customisation
    selected_settings = _render_settings(settings, reference)
    if not isinstance(path, str):
        path = _canonical_path(path)
    obj = (
        reference.get_object(path)
        if reference is not None
        else get_object(
            path, parser=selected_settings.parser, dynamic=selected_settings.dynamic or False
        )
    )
    return _render(obj, selected_settings, customisation=reference)
