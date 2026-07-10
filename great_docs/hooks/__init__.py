"""
Public registration surface for the API-reference pipeline events

Each event lives in its own module; only the `on_<event>` decorators are
public. The emitters are internal and imported from their event module.
"""

from ._object_resolved import on_object_resolved

__all__ = ["on_object_resolved"]
