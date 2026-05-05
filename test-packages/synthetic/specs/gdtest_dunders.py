"""
gdtest_dunders — Dunder method visibility.

Dimensions: A1, B1, C10, D1, E6, F6, G1, H7
Focus: 1 class with __init__, __repr__, __eq__, __len__, __getitem__.
       Tests dunder/private method filtering in method enumeration.
"""

SPEC = {
    "name": "gdtest_dunders",
    "description": "Dunder methods (__init__, __repr__, __eq__, etc.)",
    "dimensions": ["A1", "B1", "C10", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-dunders",
            "version": "0.1.0",
            "description": "A synthetic test package with dunder methods",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_dunders/__init__.py": '''\
            """A test package with dunder methods."""

            __version__ = "0.1.0"
            __all__ = ["Collection"]


            class Collection:
                """
                A custom collection with dunder methods.

                Parameters
                ----------
                items
                    Initial items for the collection.
                """

                def __init__(self, *items):
                    self._items = list(items)

                def __repr__(self) -> str:
                    """
                    String representation.

                    Returns
                    -------
                    str
                        repr string.
                    """
                    return f"Collection({self._items!r})"

                def __eq__(self, other) -> bool:
                    """
                    Check equality.

                    Parameters
                    ----------
                    other
                        The other object to compare.

                    Returns
                    -------
                    bool
                        True if equal.
                    """
                    if isinstance(other, Collection):
                        return self._items == other._items
                    return NotImplemented

                def __len__(self) -> int:
                    """
                    Get the number of items.

                    Returns
                    -------
                    int
                        Number of items.
                    """
                    return len(self._items)

                def __getitem__(self, index: int):
                    """
                    Get an item by index.

                    Parameters
                    ----------
                    index
                        The item index.

                    Returns
                    -------
                    object
                        The item at the given index.
                    """
                    return self._items[index]

                def add(self, item) -> None:
                    """
                    Add an item to the collection.

                    Parameters
                    ----------
                    item
                        The item to add.
                    """
                    self._items.append(item)

                def clear(self) -> None:
                    """Remove all items from the collection."""
                    self._items.clear()
        ''',
        "README.md": """\
            # gdtest-dunders

            A synthetic test package with dunder methods.
        """,
    },
    "expected": {
        "detected_name": "gdtest-dunders",
        "detected_module": "gdtest_dunders",
        "detected_parser": "numpy",
        "export_names": ["Collection"],
        "num_exports": 1,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
