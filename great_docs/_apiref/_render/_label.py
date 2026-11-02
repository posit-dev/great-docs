from __future__ import annotations

from typing import TYPE_CHECKING

from .._type_checks import attribute_kind, class_kind, function_kind

if TYPE_CHECKING:
    import griffe as gf


def get_label(obj: gf.Alias | gf.Object) -> str:
    if obj.is_function:
        label = _function_label(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_class:
        label = class_kind(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_type_alias or obj.is_attribute:
        label = attribute_kind(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_module:
        label = "module"
    else:
        raise ValueError("Unknown kind of object")
    return label


def _function_label(obj: gf.Function) -> str:
    if obj.parent and obj.parent.is_class:
        return "method"
    return function_kind(obj)
