"""
The `object_resolved` event — emitted per object once its reference resolves to a griffe object

A registered handler receives the resolved object and returns it (optionally
annotated or replaced), or `None` to skip it, before the API-reference resolver
builds its `Doc`. great-docs registers its own built-in handlers here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ._registry import HookRegistry

if TYPE_CHECKING:
    import griffe as gf

ObjectResolvedHook = Callable[["gf.Object | gf.Alias"], "gf.Object | gf.Alias | None"]
"""A handler that inspects, replaces, or skips a resolved object"""

REGISTRY: HookRegistry[ObjectResolvedHook] = HookRegistry()
"""The object_resolved handlers, ordered by priority"""

on_object_resolved = REGISTRY.register
"""Register a handler for the `object_resolved` event (bare or `priority=`-parameterized)"""


def emit_object_resolved(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
    """
    Emit the `object_resolved` event and return the object its handlers produce

    Handlers run in priority order (lower first, ties in registration order);
    the first to return `None` skips the object and the rest are not consulted.

    Parameters
    ----------
    obj
        The object just resolved from its reference.

    Returns
    -------
    The object to document, or `None` when a handler skips it.
    """
    for hook in REGISTRY:
        result = hook(obj)
        if result is None:
            return None
        obj = result
    return obj
