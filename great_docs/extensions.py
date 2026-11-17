"""
Project-local API-reference extension registration and callback types

Define `setup(extension)` in the configured Python entry file. Register through
that supplied owner; registrations and its project cache belong to one operation.
"""

from ._apiref._customisation import Extension, ExtensionError
from .hooks._docstring_parsed import DocstringParsedHook
from .hooks._object_resolved import ObjectResolvedHook

__all__ = [
    "DocstringParsedHook",
    "Extension",
    "ExtensionError",
    "ObjectResolvedHook",
]
