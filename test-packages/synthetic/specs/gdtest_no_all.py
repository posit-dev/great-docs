"""
gdtest_no_all — Package with pyproject.toml but no __all__.

Dimensions: A1, B3, C4, D1, E6, F6, G1, H7
Focus: Has pyproject.toml for name detection but no __all__ in __init__.py.
       Griffe discovers public names via fallback introspection.
       Tests _discover_package_exports fallback path.
"""

SPEC = {
    "name": "gdtest_no_all",
    "description": "No __all__ — griffe fallback discovery",
    "dimensions": ["A1", "B3", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-no-all",
            "version": "0.1.0",
            "description": "A synthetic test package with no __all__",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_no_all/__init__.py": '''\
            """A test package without __all__ — relies on griffe discovery."""

            __version__ = "0.1.0"


            class Registry:
                """
                A simple key-value registry.

                Parameters
                ----------
                name
                    Registry name.
                """

                def __init__(self, name: str = "default"):
                    self.name = name
                    self._items = {}

                def register(self, key: str, value) -> None:
                    """
                    Register an item.

                    Parameters
                    ----------
                    key
                        The registration key.
                    value
                        The value to register.
                    """
                    self._items[key] = value

                def lookup(self, key: str):
                    """
                    Look up an item by key.

                    Parameters
                    ----------
                    key
                        The key to look up.

                    Returns
                    -------
                    object
                        The registered value.
                    """
                    return self._items.get(key)


            def create_registry(name: str) -> Registry:
                """
                Create a new registry.

                Parameters
                ----------
                name
                    The registry name.

                Returns
                -------
                Registry
                    A new registry instance.
                """
                return Registry(name)


            def list_keys(registry: Registry) -> list:
                """
                List all keys in a registry.

                Parameters
                ----------
                registry
                    The registry to inspect.

                Returns
                -------
                list
                    List of registered keys.
                """
                return list(registry._items.keys())


            def _internal_helper():
                """This is private and should not be discovered."""
                pass
        ''',
        "README.md": """\
            # gdtest-no-all

            A synthetic test package with no ``__all__`` — griffe fallback.
        """,
    },
    "expected": {
        "detected_name": "gdtest-no-all",
        "detected_module": "gdtest_no_all",
        "detected_parser": "numpy",
        "export_names": ["Registry", "create_registry", "list_keys"],
        "num_exports": 3,
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec"],
    },
}
