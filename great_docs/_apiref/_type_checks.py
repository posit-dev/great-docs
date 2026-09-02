from __future__ import annotations

from typing import TYPE_CHECKING, cast

import griffe as gf

from . import content

if TYPE_CHECKING:
    from typing import TypeGuard

    from .typing import DocMemberType, DocType  # noqa: TCH001


def is_typealias(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a type alias

    Covers both PEP 695 ``type X = ...`` aliases, which griffe models as a
    dedicated `TypeAlias`, and explicit ``X: TypeAlias = ...`` attributes.
    """
    # `isinstance` avoids resolving aliases, which can raise for unresolved
    # targets; PEP 695 aliases are a distinct type rather than an Attribute.
    if isinstance(obj, gf.TypeAlias):
        return True
    if not (isinstance(obj, gf.Attribute) and obj.annotation):
        return False
    elif isinstance(obj.annotation, gf.ExprName):
        return obj.annotation.name == "TypeAlias"
    elif isinstance(obj.annotation, str):
        return True
    return False


def is_protocol(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a class defining a typing `Protocol`
    """
    return (
        isinstance(obj, gf.Class)
        and len(obj.bases) > 0
        and isinstance(obj.bases[-1], gf.ExprName)
        and obj.bases[-1].canonical_path == "typing.Protocol"
    )


_ENUM_BASES = frozenset({"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "ReprEnum", "EnumCheck"})


def _short_base_names(obj: gf.Class) -> set[str]:
    """
    The unqualified names of `obj`'s bases

    Reduces both bare (`Enum`) and qualified (`enum.Enum`) spellings to the
    same short name, matching the string-based comparison
    `great_docs/core.py` uses to classify the same kinds.
    """
    return {str(base).rsplit(".", 1)[-1] for base in obj.bases}


def is_typeddict(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a class declaring a `TypedDict`

    A `@dataclass`-decorated class is classified as a dataclass ahead of any
    base check in `great_docs/core.py`; matching that precedence here keeps
    a dataclass that also derives from `TypedDict` showing its constructor
    brackets.
    """
    return (
        isinstance(obj, gf.Class)
        and "dataclass" not in obj.labels
        and "TypedDict" in _short_base_names(obj)
    )


def is_enum(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a class deriving from one of the `enum` base classes

    A `@dataclass`-decorated class is classified as a dataclass ahead of any
    base check in `great_docs/core.py`; matching that precedence here keeps
    a dataclass that also derives from an `enum` base showing its
    constructor brackets.
    """
    return (
        isinstance(obj, gf.Class)
        and "dataclass" not in obj.labels
        and bool(_short_base_names(obj) & _ENUM_BASES)
    )


def is_typevar(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a declaration of a `TypeVar`
    """
    return (
        isinstance(obj, gf.Attribute)
        and hasattr(obj, "value")
        and isinstance(obj.value, gf.ExprCall)
        and isinstance(obj.value.function, gf.ExprName)
        and obj.value.function.name == "TypeVar"
    )


def is_initvar(obj: str | gf.Expr | None) -> TypeGuard[gf.ExprSubscript]:
    """
    Whether `obj` is an `InitVar` annotation
    """
    return (
        isinstance(obj, gf.ExprSubscript)
        and isinstance(obj.left, gf.ExprName)
        and obj.left.canonical_path == "dataclasses.InitVar"
    )


def is_doc_function(el: DocMemberType) -> TypeGuard[content.DocFunction]:
    """Whether the member documents a function"""
    return el.obj.is_function


def is_doc_class(el: DocMemberType) -> TypeGuard[content.DocClass]:
    """Whether the member documents a class"""
    return el.obj.is_class


def is_doc_attribute(el: DocMemberType) -> TypeGuard[content.DocAttribute]:
    """Whether the member documents an attribute"""
    return el.obj.is_attribute


def is_doc_type_alias(el: DocMemberType) -> TypeGuard[content.DocTypeAlias]:
    """Whether the member documents a type alias"""
    return el.obj.is_type_alias


def griffe_to_doc(
    obj: gf.Object | gf.Alias,
    *,
    deep: bool = True,
    inherited: bool = True,
    skip_aliases: bool = False,
) -> DocType:
    """
    Convert a griffe object to a documentable type

    By default all members, including inherited ones, are included
    recursively. `inherited=False` limits members to those defined on the
    object itself; `skip_aliases=True` leaves out members that are aliases
    (e.g. imported names).
    """
    members = None
    if deep:
        member_map = obj.all_members if inherited else obj.members
        members = [
            griffe_to_doc(m, inherited=inherited, skip_aliases=skip_aliases)
            for m in member_map.values()
            if not (skip_aliases and isinstance(m, gf.Alias))
        ]
    return content.Doc.from_griffe(obj.name, obj, members=members)  # pyright: ignore[reportUnknownMemberType]


def is_field_init_false(el: gf.Parameter) -> bool:
    """
    Whether `el` is a `field(init=False, ...)` expression
    """
    if not (
        isinstance(el.default, gf.ExprCall)
        and isinstance(el.default.function, gf.ExprName)
        and el.default.function.name == "field"
    ):
        return False

    # field has only keyword arguments
    exprs = cast("list[gf.ExprKeyword]", el.default.arguments)
    return any(expr.value == "False" for expr in exprs if expr.name == "init")
