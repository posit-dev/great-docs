from __future__ import annotations

from typing import TYPE_CHECKING

from .._type_checks import class_kind, function_kind, is_typevar

if TYPE_CHECKING:
    import griffe as gf


def get_label(obj: gf.Alias | gf.Object) -> str:
    if obj.is_function:
        label = _function_label(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_class:
        label = class_kind(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_type_alias:
        # A PEP 695 alias has no `annotation`, and may arrive as an `Alias`
        # proxy rather than a `TypeAlias`, so decide it here by predicate.
        label = "typealias"
    elif obj.is_attribute:
        label = _attribute_label(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_module:
        label = "module"
    else:
        raise ValueError("Unknown kind of object")
    return label


def _attribute_label(obj: gf.Attribute) -> str:
    annotation = obj.annotation
    annotation_path = (
        annotation.canonical_path if annotation and not isinstance(annotation, str) else annotation
    )

    if annotation_path in {"TypeAlias", "typing.TypeAlias"}:
        return "typealias"
    annotation_text = str(annotation) if annotation else ""
    if (
        "TypeVar" in annotation_text
        or "ParamSpec" in annotation_text
        or "TypeVarTuple" in annotation_text
        or is_typevar(obj)
    ):
        return "typevar"
    elif "property" in obj.labels:
        return "property"

    return "constant"


def _function_label(obj: gf.Function) -> str:
    if obj.parent and obj.parent.is_class:
        return "method"
    return function_kind(obj)
