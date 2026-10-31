from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

import griffe as gf

from . import content

if TYPE_CHECKING:
    from typing import TypeGuard

    from .typing import DocMemberType, DocType  # noqa: TCH001


def _resolved(obj: gf.Object | gf.Alias) -> gf.Object | None:
    """
    Resolve `obj` to the object at the end of its alias chain

    Re-exported objects arrive as `Alias` instances, so kind checks inspect
    the object at the end of the alias chain. Return `None` when that target
    cannot be loaded, allowing predicates to return `False` instead of
    raising.

    Parameters
    ----------
    obj :
        The node to resolve.

    Returns
    -------
    :
        The resolved object, or `None` when its target is unreachable.
    """
    if isinstance(obj, gf.Alias):
        try:
            return obj.final_target
        except (gf.AliasResolutionError, gf.CyclicAliasError):
            return None
    return obj


def _as_class(obj: gf.Object | gf.Alias) -> gf.Class | None:
    """
    Resolve `obj` to a class, or return `None` for another kind of object

    Parameters
    ----------
    obj :
        The node to resolve.

    Returns
    -------
    :
        The resolved class, or `None`.
    """
    target = _resolved(obj)
    return target if isinstance(target, gf.Class) else None


def is_typealias(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a type alias

    Covers both PEP 695 ``type X = ...`` aliases, which griffe models as a
    dedicated `TypeAlias`, and explicit ``X: TypeAlias = ...`` attributes.
    """
    target = _resolved(obj)
    if isinstance(target, gf.TypeAlias):
        return True
    if not (isinstance(target, gf.Attribute) and target.annotation):
        return False
    elif isinstance(target.annotation, gf.ExprName):
        return target.annotation.name == "TypeAlias"
    elif isinstance(target.annotation, str):
        return True
    return False


def is_protocol(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a class defining a typing `Protocol`
    """
    cls = _as_class(obj)
    return (
        cls is not None
        and len(cls.bases) > 0
        and isinstance(cls.bases[-1], gf.ExprName)
        and cls.bases[-1].canonical_path == "typing.Protocol"
    )


_ENUM_BASES = frozenset({"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "ReprEnum", "EnumCheck"})

_EXCEPTION_BASES = frozenset(
    {
        "Exception",
        "BaseException",
        # Built-in error types
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "BlockingIOError",
        "BrokenPipeError",
        "BufferError",
        "BytesWarning",
        "ChildProcessError",
        "ConnectionAbortedError",
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "DeprecationWarning",
        "EOFError",
        "EnvironmentError",
        "FileExistsError",
        "FileNotFoundError",
        "FloatingPointError",
        "FutureWarning",
        "GeneratorExit",
        "IOError",
        "ImportError",
        "ImportWarning",
        "IndentationError",
        "IndexError",
        "InterruptedError",
        "IsADirectoryError",
        "KeyError",
        "KeyboardInterrupt",
        "LookupError",
        "MemoryError",
        "ModuleNotFoundError",
        "NameError",
        "NotADirectoryError",
        "NotImplementedError",
        "OSError",
        "OverflowError",
        "PendingDeprecationWarning",
        "PermissionError",
        "ProcessLookupError",
        "RecursionError",
        "ReferenceError",
        "ResourceWarning",
        "RuntimeError",
        "RuntimeWarning",
        "StopAsyncIteration",
        "StopIteration",
        "SyntaxError",
        "SyntaxWarning",
        "SystemError",
        "SystemExit",
        "TabError",
        "TimeoutError",
        "TypeError",
        "UnboundLocalError",
        "UnicodeDecodeError",
        "UnicodeEncodeError",
        "UnicodeError",
        "UnicodeTranslationError",
        "UnicodeWarning",
        "UserWarning",
        "ValueError",
        "Warning",
        "ZeroDivisionError",
    }
)

ClassKind = Literal[
    "dataclass", "enum", "exception", "namedtuple", "typeddict", "protocol", "abc", "class"
]
FunctionKind = Literal["async", "classmethod", "staticmethod", "property", "function"]
AttributeKind = Literal["type_alias", "typevar", "constant"]


def _short_base_names(obj: gf.Class | gf.Alias) -> set[str]:
    """
    Return the unqualified names of the bases of `obj`

    Reduce both bare (`Enum`) and qualified (`enum.Enum`) spellings to the
    same short name.

    Parameters
    ----------
    obj :
        A class, or an alias to one.

    Returns
    -------
    :
        The short base names.
    """
    return {str(base).rsplit(".", 1)[-1] for base in obj.bases}


def class_kind(obj: gf.Class | gf.Alias) -> ClassKind:
    """
    Classify a class by its labels and the names of its bases

    The first rule that matches decides: the `dataclass` label, an `enum`
    base, a built-in exception base, `NamedTuple`, `TypedDict`, `Protocol` or
    `runtime_checkable`, then an `ABC` or `ABCMeta` base.

    Parameters
    ----------
    obj :
        A class, or an alias whose target is a class.

    Returns
    -------
    :
        The kind of class, or `"class"` when no rule matches.
    """
    if "dataclass" in obj.labels:
        return "dataclass"

    bases = _short_base_names(obj)
    if bases & _ENUM_BASES:
        return "enum"
    if bases & _EXCEPTION_BASES:
        return "exception"
    if "NamedTuple" in bases:
        return "namedtuple"
    if "TypedDict" in bases:
        return "typeddict"
    if "Protocol" in bases or "runtime_checkable" in bases:
        return "protocol"
    if bases & {"ABC", "ABCMeta"}:
        return "abc"
    return "class"


def function_kind(obj: gf.Function | gf.Alias) -> FunctionKind:
    """
    Classify a function by its griffe labels

    The first label that matches decides: `async`, `classmethod`,
    `staticmethod`, then `property`.

    Parameters
    ----------
    obj :
        A function, or an alias whose target is a function.

    Returns
    -------
    :
        The kind of function, or `"function"` when no label matches.
    """
    labels = obj.labels
    if "async" in labels:
        return "async"
    if "classmethod" in labels:
        return "classmethod"
    if "staticmethod" in labels:
        return "staticmethod"
    if "property" in labels:
        return "property"
    return "function"


def attribute_kind(obj: gf.Attribute | gf.TypeAlias | gf.Alias) -> AttributeKind:
    """
    Classify a module-level attribute or type alias

    A PEP 695 `type` statement is a type alias. An attribute declares a type
    variable when its annotation names `TypeVar`, `ParamSpec` or
    `TypeVarTuple`, or when its value calls one of them.

    Parameters
    ----------
    obj :
        An attribute or type alias, or an alias whose target is one.

    Returns
    -------
    :
        The kind of attribute, or `"constant"` when no rule matches.
    """
    # An alias to a type alias is not a `gf.TypeAlias` instance; its kind is.
    if isinstance(obj, gf.TypeAlias) or obj.kind is gf.Kind.TYPE_ALIAS:
        return "type_alias"
    annotation = str(obj.annotation) if obj.annotation else ""
    if any(kind in annotation for kind in _TYPE_VARIABLE_KINDS) or is_typevar(obj):
        return "typevar"
    return "constant"


def is_typeddict(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a class that `class_kind` classifies as a `TypedDict`

    A `@dataclass`-decorated class that also derives from `TypedDict` is a
    dataclass, so it keeps its constructor brackets.
    """
    cls = _as_class(obj)
    return cls is not None and class_kind(cls) == "typeddict"


def is_enum(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a class that `class_kind` classifies as an enum

    A `@dataclass`-decorated class that also derives from an `enum` base is a
    dataclass, so it keeps its constructor brackets.
    """
    cls = _as_class(obj)
    return cls is not None and class_kind(cls) == "enum"


_TYPE_VARIABLE_KINDS = frozenset({"TypeVar", "ParamSpec", "TypeVarTuple"})


def is_typevar(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether `obj` is a declaration of a type variable

    A type variable is a `TypeVar`, `ParamSpec` or `TypeVarTuple`, called by
    its bare name or through any module, such as `typing.TypeVar`.
    """
    target = _resolved(obj)
    if not (isinstance(target, gf.Attribute) and isinstance(target.value, gf.ExprCall)):
        return False
    function = target.value.function
    return (
        isinstance(function, (gf.ExprName, gf.ExprAttribute))
        and function.canonical_path.rpartition(".")[2] in _TYPE_VARIABLE_KINDS
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
    return content.Doc.from_griffe(obj.name, obj, members=members)


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
