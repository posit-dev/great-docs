"""
The extension that a project's `setup(extension)` receives, and its hook types

The file named by `api_reference_extension` defines `setup(extension)`. Setup uses the
`Extension` it receives to register object and docstring hooks, select `Renderers`
from `great_docs.rendering` and declare the inputs it reads.
Registration closes when setup returns. The extension and its `cache` last for one
generation of the API reference.

Semantic results and exclusions are shared across aliases. Limit semantic edits
to the current object's documentation and metadata. Use a custom renderer for
appearance-specific content. Configured failures raise
`ExtensionError` with their original cause and release owned imports.
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
