"""
The global registry of object hooks, which every API reference extension copies

A handler receives each object before Great Docs parses its docstring, and returns
the object, a replacement, or `None` to exclude it. Great Docs registers its built-in
handlers here; a project registers its own through `Extension.on_object_resolved`.
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
"""
Register a global object hook, which every extension created afterwards copies

The hook runs on each object before Great Docs parses its docstring. It may inspect,
mutate or replace the object, or return `None` to exclude it. After the hooks run,
Great Docs clears the object's parsed-docstring cache, so parsing reads the final
`docstring.value`. Extension files register through `Extension.on_object_resolved`
instead; registering here from one fails.
"""
