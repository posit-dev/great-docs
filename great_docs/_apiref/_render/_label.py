from __future__ import annotations

from typing import TYPE_CHECKING

from .._type_checks import is_typevar

if TYPE_CHECKING:
    import griffe as gf

ENUMS = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "ReprEnum", "EnumCheck"}
EXCEPTIONS = {
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
    "DeprecationWarning",
    "ValueError",
    "Warning",
    "ZeroDivisionError",
}


def get_label(obj: gf.Alias | gf.Object) -> str:
    if obj.is_function:
        label = _function_label(obj)  # pyright: ignore[reportArgumentType]
    elif obj.is_class:
        label = _class_label(obj)  # pyright: ignore[reportArgumentType]
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
    labels = obj.labels

    if obj.parent and obj.parent.is_class:
        return "method"
    if "async" in labels:
        return "async"
    if "classmethod" in labels:
        return "classmethod"
    if "staticmethod" in labels:
        return "staticmethod"
    if "property" in labels:
        return "property"
    return "function"


def _class_label(obj: gf.Class) -> str:
    labels = obj.labels
    if "dataclass" in labels:
        return "dataclass"
    try:
        # Normalize base names: "enum.IntEnum" → "IntEnum"
        bases: set[str] = {str(b).rsplit(".", 1)[-1] for b in obj.bases}
    except Exception:
        bases = set()

    if bases & ENUMS:
        return "enum"
    elif bases & EXCEPTIONS:
        return "exception"
    elif "NamedTuple" in bases:
        return "namedtuple"
    elif "TypedDict" in bases:
        return "typeddict"
    elif "Protocol" in bases or "runtime_checkable" in bases:
        return "protocol"
    elif bases & {"ABC", "ABCMeta"}:
        return "abc"

    return "class"
