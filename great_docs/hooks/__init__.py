"""Registration decorators for API-reference events"""

from ._docstring_parsed import on_docstring_parsed
from ._object_resolved import on_object_resolved

__all__ = ["on_docstring_parsed", "on_object_resolved"]
