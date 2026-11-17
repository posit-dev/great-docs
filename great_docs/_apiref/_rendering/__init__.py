"""Built-in API reference renderers and scoped renderer choices"""

from ._renderers import Renderers
from .api_pages import APIPageRenderer
from .attributes import AttributeRenderer
from .base import BaseRenderer
from .classes import ClassRenderer
from .functions import FunctionRenderer
from .modules import ModuleRenderer
from .objects import ObjectRenderer
from .reference_index import ReferenceIndexRenderer
from .reference_sections import ReferenceSectionRenderer
from .type_aliases import TypeAliasRenderer

__all__ = (
    "Renderers",
    "APIPageRenderer",
    "BaseRenderer",
    "ObjectRenderer",
    "AttributeRenderer",
    "ClassRenderer",
    "FunctionRenderer",
    "ModuleRenderer",
    "TypeAliasRenderer",
    "ReferenceIndexRenderer",
    "ReferenceSectionRenderer",
)
