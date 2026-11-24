"""
The global registry of docstring hooks, which every API reference extension copies

A handler runs after Griffe parses an object's final docstring and before Great Docs
builds the object's documentation. Objects without docstrings skip it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from ._registry import HookRegistry

if TYPE_CHECKING:
    import griffe as gf

DocstringParsedHook = Callable[
    ["gf.Object | gf.Alias", "list[gf.DocstringSection]"],
    "list[gf.DocstringSection]",
]
"""A handler that customises the parsed sections of a resolved object"""

REGISTRY: HookRegistry[DocstringParsedHook] = HookRegistry()
"""The `docstring_parsed` handlers, ordered by priority"""

on_docstring_parsed = REGISTRY.register
"""
Register a global docstring hook, which every extension created afterwards copies

The hook runs after Griffe parses an object's final docstring and before Great Docs
builds the object's documentation. It receives the object and its parsed sections
and returns the sections to keep. Objects without docstrings skip it. Extension
files register through `Extension.on_docstring_parsed` instead; registering here
from one fails.
"""
