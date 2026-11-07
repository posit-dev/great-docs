"""
Extending the rendering
"""

from __future__ import annotations

from functools import cached_property
from types import CellType, FunctionType, MethodType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, TypeVar

    from .base import RenderBase

    T = TypeVar("T")


def extend_base_class(cls: type[RenderBase]):
    """
    Copy the methods & attributes defined in `cls` into its immediate base class

    This helps with customising the Render classes

    Parameters
    ----------
    cls :
        Class defined by the user that is subclassing an extension
        point (empty base class).

    See Also
    --------
    great_docs.renderer.RenderDocClass, great_docs.renderer.RenderDocFunction,
        great_docs.renderer.RenderDocAttribute,
        great_docs.renderer.RenderDocModule : Classes you are most likely to extend.
    """
    # Attributes that should not be copied when extending a base class
    exclude = {"__module__", "__dict__", "__weakref__", "__doc__"}
    base = cls.mro()[1]
    attrs = [name for name in vars(cls) if name not in exclude]
    for name in attrs:
        set_class_attr(base, name, getattr(cls, name))


def set_class_attr(cls: type[RenderBase], name: str, value: Any):
    """
    Set a class attribute, with proper handling of `super()` in functions and properties

    Unlike the builtin setattr, this function ensures that values
    that are functions/methods or properties that use super() will
    work properly on the class they are attached to.

    Parameters
    ----------
    cls :
        Class on which to attach the attribute
    name :
        Name of attribute.
    value :
        The value to set the attribute to.
    """

    # When a method uses super(), the python compiler wraps that method as
    # a closure over the __class__ in which the method is defined. If a
    # function is a closure, we rebuild it with __class__ changed to the
    # class being attached to.
    def adjust_closure(obj: T) -> T:
        """Adjust the `__class__` closure for a function"""
        if isinstance(obj, FunctionType) and obj.__closure__:
            obj = FunctionType(
                obj.__code__.replace(co_freevars=("__class__",)),
                obj.__globals__,
                closure=(CellType(cls),),
            )
        return obj

    if isinstance(value, property):
        # Adjust all methods of a property and recreate it
        fget = adjust_closure(value.fget)
        fset = adjust_closure(value.fset)
        fdel = adjust_closure(value.fdel)
        value = property(fget=fget, fset=fset, fdel=fdel, doc=value.__doc__)
    elif isinstance(value, cached_property):
        func = adjust_closure(value.func)
        value = cached_property(func)  # pyright: ignore[reportUnknownVariableType]
        value.__set_name__(cls, name)
    elif isinstance(value, MethodType):
        # This is for @staticmethods
        func = adjust_closure(value.__func__)
        value = MethodType(func, cls)
    else:
        value = adjust_closure(value)

    setattr(cls, name, value)
