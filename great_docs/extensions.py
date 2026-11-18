"""
The extension that a project's `setup(extension)` receives, and its hook types

The file named by `api_reference_extension` defines `setup(extension)`. Setup uses the
`Extension` it receives to register object and docstring hooks, select `Renderers`
from `great_docs.rendering` and declare the inputs it reads.
Registration closes when setup returns. The extension and its `cache` last for one
generation of the API reference.

Every alias of an object shares the result of its object and docstring hooks,
including an exclusion, so limit those edits to the object's own docstring and
metadata. To customise an object on a particular page, use a renderer and consult
its `context`.

A failure in extension code raises `ExtensionError`, chained to the original error.
The project modules the extension imported are released when the run ends.
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
