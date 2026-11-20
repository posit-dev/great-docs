"""
Python reference discovery and rendering from inspected API objects

Share source and metadata values with content processing; keep website assembly
out of reference rendering.
"""

from ._rendering.api_pages import APIPageRenderer
from ._rendering.attributes import AttributeRenderer
from ._rendering.callables import CallableRendererMixin
from ._rendering.classes import ClassRenderer
from ._rendering.functions import FunctionRenderer
from ._rendering.members import MembersRendererMixin
from ._rendering.modules import ModuleRenderer
from ._rendering.objects import ObjectRenderer
from ._rendering.reference_index import ReferenceIndexRenderer
from ._rendering.reference_sections import ReferenceSectionRenderer
from ._rendering.type_aliases import TypeAliasRenderer

# Re-exports from the _apiref submodules
from .api_reference import APIReference
from .collect import build_manifest, remove_package_prefix
from .introspect import get_object
from .inventory import create_inventory, write_inventory
from .spec import SpecObject

__all__ = (
    "ObjectRenderer",
    "ClassRenderer",
    "FunctionRenderer",
    "AttributeRenderer",
    "ModuleRenderer",
    "TypeAliasRenderer",
    "CallableRendererMixin",
    "MembersRendererMixin",
    "ReferenceIndexRenderer",
    "APIPageRenderer",
    "ReferenceSectionRenderer",
    "get_object",
    "APIReference",
    "remove_package_prefix",
    "build_manifest",
    "create_inventory",
    "write_inventory",
    "SpecObject",
)
