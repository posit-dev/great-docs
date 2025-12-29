from __future__ import annotations

from dataclasses import field
from typing import TYPE_CHECKING, cast

import griffe as gf
from quartodoc import layout

if TYPE_CHECKING:
    from typing import TypeGuard, TypeVar

    from .typing import DocMemberType, DocType  # noqa: TCH001

    T = TypeVar("T")


def is_typealias(obj: gf.Object | gf.Alias) -> bool:
    """
    Return True if obj is a declaration of a TypeAlias
    """
    # TODO:
    # Figure out if this handles new-style typealiases introduced
    # in python 3.12 to handle
    if not (isinstance(obj, gf.Attribute) and obj.annotation):
        return False
    elif isinstance(obj.annotation, gf.ExprName):
        return obj.annotation.name == "TypeAlias"
    elif isinstance(obj.annotation, str):
        return True
    return False


def is_protocol(obj: gf.Object | gf.Alias) -> bool:
    """
    Return True if obj is a class defining a typing Protocol
    """
    return (
        isinstance(obj, gf.Class)
        and len(obj.bases) > 0
        and isinstance(obj.bases[-1], gf.ExprName)
        and obj.bases[-1].canonical_path == "typing.Protocol"
    )


def is_typevar(obj: gf.Object | gf.Alias) -> bool:
    """
    Return True if obj is a declaration of a TypeVar
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
    Return True if object is an an InitVar annotation
    """
    return (
        isinstance(obj, gf.ExprSubscript)
        and isinstance(obj.left, gf.ExprName)
        and obj.left.canonical_path == "dataclasses.InitVar"
    )


class isDoc:
    """
    TypeGuards for layout.Doc objects
    """

    @staticmethod
    def Function(el: DocMemberType) -> TypeGuard[layout.DocFunction]:
        return el.obj.is_function  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]

    @staticmethod
    def Class(el: DocMemberType) -> TypeGuard[layout.DocClass]:
        return el.obj.is_class  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]

    @staticmethod
    def Attribute(el: DocMemberType) -> TypeGuard[layout.DocAttribute]:
        return el.obj.is_attribute  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]

    @staticmethod
    def Module(el: DocMemberType) -> TypeGuard[layout.DocModule]:
        return el.obj.is_attribute  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]


def griffe_to_doc(obj: gf.Object | gf.Alias, *, deep: bool = True) -> DocType:
    """
    Convert griffe object to a quartodoc documentable type

    The function recursively includes all members.
    """
    members = [griffe_to_doc(m, deep=deep) for m in obj.all_members.values()] if deep else None
    return layout.Doc.from_griffe(obj.name, obj, members=members)  # pyright: ignore[reportUnknownMemberType]


def no_init(default: T) -> T:
    """
    Set defaut value of a dataclass field that will not be __init__ed
    """
    return field(init=False, default=default)


def is_field_init_false(el: gf.Parameter) -> bool:
    """
    Return True if parameter is a field(init=False, ...) expression
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
