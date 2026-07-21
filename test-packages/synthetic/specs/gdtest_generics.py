"""
gdtest_generics — Generic classes with TypeVar.

Dimensions: A1, B1, C20, D1, E6, F6, G1, H7
Focus: Generic classes using TypeVar to verify parameterized types
       render correctly in documentation.
"""

SPEC = {
    "name": "gdtest_generics",
    "description": "Generic classes with TypeVar",
    "dimensions": ["A1", "B1", "C20", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-generics",
            "version": "0.1.0",
            "description": "Test generic class documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_generics/__init__.py": '''\
            """Package with generic classes."""

            from typing import TypeVar, Generic, Optional, List

            __version__ = "0.1.0"
            __all__ = ["Stack", "Pair"]

            T = TypeVar("T")
            K = TypeVar("K")
            V = TypeVar("V")


            class Stack(Generic[T]):
                """
                A generic stack data structure.

                Parameters
                ----------
                items
                    Initial items for the stack.
                """

                def __init__(self, items: Optional[List[T]] = None):
                    self._items: List[T] = list(items) if items else []

                def push(self, item: T) -> None:
                    """
                    Push an item onto the stack.

                    Parameters
                    ----------
                    item
                        Item to push.
                    """
                    self._items.append(item)

                def pop(self) -> T:
                    """
                    Pop the top item from the stack.

                    Returns
                    -------
                    T
                        The item removed from the top.

                    Raises
                    ------
                    IndexError
                        If the stack is empty.
                    """
                    return self._items.pop()

                def peek(self) -> T:
                    """
                    View the top item without removing it.

                    Returns
                    -------
                    T
                        The top item.
                    """
                    return self._items[-1]

                def is_empty(self) -> bool:
                    """
                    Check if the stack is empty.

                    Returns
                    -------
                    bool
                        True if empty.
                    """
                    return len(self._items) == 0


            class Pair(Generic[K, V]):
                """
                A generic key-value pair.

                Parameters
                ----------
                key
                    The key.
                value
                    The value.
                """

                def __init__(self, key: K, value: V):
                    self.key = key
                    self.value = value

                def swap(self) -> "Pair[V, K]":
                    """
                    Return a new Pair with key and value swapped.

                    Returns
                    -------
                    Pair[V, K]
                        Swapped pair.
                    """
                    return Pair(self.value, self.key)
        ''',
        "README.md": """\
            # gdtest-generics

            Tests generic classes with TypeVar documentation.
        """,
    },
    "expected": {
        "detected_name": "gdtest-generics",
        "detected_module": "gdtest_generics",
        "detected_parser": "numpy",
        "export_names": ["Stack", "Pair"],
        "num_exports": 2,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
