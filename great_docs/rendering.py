"""
API reference renderers and their context

To change presentation, subclass a renderer, collect the subclasses in `Renderers`
and pass them to `Extension.set_renderers` during setup. The subclasses apply to that
run only and never change the built-in classes. Override the `render_*` methods
rather than cached properties such as `title` and `body`. Return `None` to omit a
block, or an empty sequence to omit summary rows.

An object renderer's `context` describes the appearance it is rendering, including
the object's authored name and its containing page.
"""

from ._apiref._rendering import (
    APIPageRenderer,
    AttributeRenderer,
    BaseRenderer,
    ClassRenderer,
    FunctionRenderer,
    ModuleRenderer,
    ObjectRenderer,
    ReferenceIndexRenderer,
    ReferenceSectionRenderer,
    Renderers,
    TypeAliasRenderer,
)
from ._apiref._rendering._context import RenderContext

__all__ = (
    "APIPageRenderer",
    "AttributeRenderer",
    "BaseRenderer",
    "ClassRenderer",
    "FunctionRenderer",
    "ModuleRenderer",
    "ObjectRenderer",
    "ReferenceIndexRenderer",
    "ReferenceSectionRenderer",
    "RenderContext",
    "Renderers",
    "TypeAliasRenderer",
)
