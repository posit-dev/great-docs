"""
Extending the rendering
"""

from __future__ import annotations

from functools import cached_property
from types import CellType, FunctionType, MethodType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any, TypeVar

    from .base import RenderBase

    T = TypeVar("T")


def extend_base_class(cls: type[RenderBase]):
    """
    Copy methods & attributes defined in cls into it's immediate base class

    This helps with customising the Render classes

    Parameters
    ----------
    cls :
        Class defined by the user that is subclassing an extension
        point (empty base class).

    See Also
    --------
    great_docs.renderer.Renderer : The bridge between these renderers and
        quartodoc's main renderer.

    great_docs.renderer.RenderDocClass, great_docs.renderer.RenderDocFunction,
        great_docs.renderer.RenderDocAttribute,
        great_docs.renderer.RenderDocModule : Classes
        you are most likely to extend.
    """
    # Attributes that should not be copied when extending a base class
    exclude = {"__module__", "__dict__", "__weakref__", "__doc__"}
    base = cls.mro()[1]
    attrs = [name for name in vars(cls) if name not in exclude]
    for name in attrs:
        set_class_attr(base, name, getattr(cls, name))


def set_class_attr(cls: type[RenderBase], name: str, value: Any):
    """
    Set class attribute

    Properly handles super() in functions and properties.

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
        """Adjust __class__ closure for a function"""
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


def exclude_parameters(spec: dict[str, str | Sequence[str]]):
    """
    Exclude the parameters of functions/class in the documentation

    When a function has a deprecated parameter, we may want to exclude it from
    the documentation. Use this function in your `_renderer.py` file to
    specify them.

    Parameters
    ----------
    spec :
        Object path and the parameter(s) to exclude.
        The object path is as shown on the API page and _not_ the
        canonical path.


    Examples
    --------
    Assuming we are documenting `package` and we want to modify these
    signatures where some parameters are deprecated:

    ```python
    ClassA(p1, p2)          # deprecated: p1
    ClassB(p1, p2, p3, p4)  # deprecated: p1, p2
    nice_function(a, b, c)  # deprecated: c
    ```

    We would use

    ```python
    from great_docs.renderer import exclude_parameters

    exclude_parameters({
        "package.ClassA": "p1",
        "package.ClassB": ("p1", "p2")
        "package.nice_function": "c"
    })
    ```

    and the documentation would have:

    ```python
    ClassA(p2)
    ClassB(p3, p4)
    nice_function(a, b)
    ```

    Notes
    -----
    When you exclude the parameter of a dataclass, it will show up in the
    attributes unless you use
    [](`~great_docs.renderer.exclude_attributes`)
    to remove it from there as well.
    """
    from .._globals import EXCLUDE_PARAMETERS

    EXCLUDE_PARAMETERS.update(spec)


def exclude_attributes(spec: dict[str, str | Sequence[str]]):
    """
    Exclude the parameters of functions/class in the documentation

    When a function has a deprecated attribute, we may want to exclude it from
    the documentation. Use this function in your `_renderer.py` file to
    specify them.

    Parameters
    ----------
    spec :
        Parent object path and the attribute(s) to exclude.
        The object path is as shown on the API page and _not_ the
        canonical path. e.g.

    Examples
    --------
    Assuming we are documenting `ClassA` and `ClassB` with the deprecated
    attributes marked as shown below.

    ```python
    class ClassA:
        a: int = 1
        b: str = "rock"
        c: bool = False   # deprecated

    class ClassB:
        a: int = 1
        b: str = "paper"  # deprecated

        @property
        def value(self):  # deprecated
            return 1
    ```

    We would use this to exclude the attributes from the documentation.

    ```python
    from great_docs.renderer import exclude_attributes

    exclude_attributes({
        "package.ClassA": "c",
        "package.ClassB": ("b", "value")
    })
    ```
    """
    from .._globals import EXCLUDE_ATTRIBUTES

    EXCLUDE_ATTRIBUTES.update(spec)


def exclude_functions(spec: dict[str, str | Sequence[str]]):
    """
    Exclude the methods of a class or functions of a module from documentation

    When a class has deprecated method(s) or a module has deprecated
    function(s), we may want to exclude them from the documentation.
    Use this function in your `_renderer.py` file to specify them.

    Parameters
    ----------
    spec :
        Parent object path and the function(s) to exclude.
        The object path is as shown on the API page and _not_ the
        canonical path. e.g.

    Examples
    --------
    If we are documenting `ClassA` with the deprecated methods marked as
    shown below.

    ```python
    class ClassA:
        def func_a(self):  # deprecated
            return "a"

        def func_b(self):
            return "b"
    ```

    We would use this to exclude the functions from being listed in the
    documentation.

    ```python
    from great_docs.renderer import exclude_functions

    exclude_functions({
        "package.ClassA": "func_a",
    })
    ```
    """
    from .._globals import EXCLUDE_FUNCTIONS

    EXCLUDE_FUNCTIONS.update(spec)


def exclude_classes(spec: dict[str, str | Sequence[str]]):
    """
    Exclude the classes in a class or module from the documentation

    When a class or module has deprecated classes or a module has
    deprecated classes, we may want to exclude them from the
    documentation. Use this function in your `_renderer.py` file
    to specify them.

    Parameters
    ----------
    spec :
        Parent object path and the class(es) to exclude.
        The object path is as shown on the API page and _not_ the
        canonical path. e.g.

    Examples
    --------
    Assuming we are documenting `ClassA` with the deprecated
    contained class marked as shown below.

    ```python
    class ClassA:
        class Contained1:  # deprecated
            pass
        class Contained2:
            pass
    ```

    We would use this to exclude the class from the documentation.

    ```python
    from great_docs.renderer import exclude_classes

    exclude_classes({
        "package.ClassA": "Contained1",
    })
    ```
    """
    from .._globals import EXCLUDE_CLASSES

    EXCLUDE_CLASSES.update(spec)
