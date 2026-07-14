"""
Great-docs' own handlers for the pipeline events

Importing this package imports each handler submodule, which registers its
handlers as a side effect.
"""

from . import _directives  # noqa: F401  — registers its object_resolved handler

__all__: list[str] = []
