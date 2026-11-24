"""Kind labels for Python objects, such as `method`, `dataclass` and `typevar`"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._type_checks import attribute_kind, class_kind, function_kind

if TYPE_CHECKING:
    import griffe as gf


def get_label(obj: gf.Alias | gf.Object) -> str:
    """
    Choose the kind label for a Python object or authored alias

    Class and attribute labels distinguish kinds such as dataclasses, protocols and
    type aliases, and a function defined in a class is labelled `method`.

    Parameters
    ----------
    obj
        The object or alias to label.

    Returns
    -------
    :
        The kind label.

    Raises
    ------
    ValueError
        If the object is not a function, class, attribute, type alias or module.
    """
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
    """
    Label a function defined in a class `method`, and any other by its function kind

    Parameters
    ----------
    obj
        The function.

    Returns
    -------
    :
        `"method"`, or the function kind.
    """
    if obj.parent and obj.parent.is_class:
        return "method"
    return function_kind(obj)
