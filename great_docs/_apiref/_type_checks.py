from __future__ import annotations

import os
from dataclasses import field
from functools import lru_cache
from typing import TYPE_CHECKING, cast

import griffe as gf

from . import content

if TYPE_CHECKING:
    from typing import Literal, TypeGuard, TypeVar

    from .typing import DocMemberType, DocType  # noqa: TCH001

    T = TypeVar("T")


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


class isDoc:
    """
    TypeGuards for nodes.Doc objects
    """

    @staticmethod
    def Function(el: DocMemberType) -> TypeGuard[content.DocFunction]:
        return el.obj.is_function

    @staticmethod
    def Class(el: DocMemberType) -> TypeGuard[content.DocClass]:
        return el.obj.is_class

    @staticmethod
    def Attribute(el: DocMemberType) -> TypeGuard[content.DocAttribute]:
        return el.obj.is_attribute

    @staticmethod
    def Module(el: DocMemberType) -> TypeGuard[content.DocModule]:
        return el.obj.is_attribute


def griffe_to_doc(obj: gf.Object | gf.Alias, *, deep: bool = True) -> DocType:
    """
    Convert a griffe object to a documentable type

    The function recursively includes all members.
    """
    members = [griffe_to_doc(m, deep=deep) for m in obj.all_members.values()] if deep else None
    return content.Doc.from_griffe(obj.name, obj, members=members)  # pyright: ignore[reportUnknownMemberType]


def no_init(default: T) -> T:
    """
    Set the default value of a dataclass field that will not be `__init__`ed
    """
    return field(init=False, default=default)


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


@lru_cache(4)
def package_info(
    key: Literal["GITHUB_REPO_URL", "GIT_REF", "PACKAGE_ROOT", "SOURCE_PATH"],
) -> str | None:
    """
    Look up a piece of package metadata by `key`

    This information has been put into the environment GreatDocs.__init___

    Returns
    -------
    str | None
        A information or None.
    """
    return os.environ.get(key, None)
