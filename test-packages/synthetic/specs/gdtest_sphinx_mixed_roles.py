"""
gdtest_sphinx_mixed_roles — Mix of ALL Sphinx role types.

Dimensions: L14
Focus: A class, functions, and docstrings using :py:class:, :py:func:,
       :py:meth:, :py:exc:, and :py:attr: roles throughout.
"""

SPEC = {
    "name": "gdtest_sphinx_mixed_roles",
    "description": "Mix of all Sphinx cross-reference role types",
    "dimensions": ["L14"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sphinx-mixed-roles",
            "version": "0.1.0",
            "description": "Test mixed Sphinx role rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_sphinx_mixed_roles/__init__.py": '''\
            """Package demonstrating mixed Sphinx cross-reference roles."""

            __version__ = "0.1.0"
            __all__ = ["Registry", "register", "lookup", "validate_entry"]


            class Registry:
                """
                A registry that maps names to types.

                Use :py:func:`register` to add entries, or call
                :py:meth:`Registry.get` directly.

                Parameters
                ----------
                strict
                    If True, raises :py:exc:`KeyError` on missing lookups.
                """

                def __init__(self, strict: bool = False):
                    self.strict = strict
                    self._entries: dict = {}

                def get(self, name: str) -> type:
                    """
                    Get a registered type by name.

                    Checks :py:attr:`Registry.strict` to decide behavior on
                    missing keys. Raises :py:exc:`KeyError` if strict mode
                    is enabled and the name is not found.

                    Parameters
                    ----------
                    name
                        The registered name to look up.

                    Returns
                    -------
                    type
                        The registered type.

                    Raises
                    ------
                    KeyError
                        If the name is not registered and strict mode is on.
                    """
                    if name in self._entries:
                        return self._entries[name]
                    if self.strict:
                        raise KeyError(name)
                    return type(None)

                def add(self, name: str, cls: type) -> None:
                    """
                    Add a type to the registry.

                    See also :py:func:`register` for the module-level helper.

                    Parameters
                    ----------
                    name
                        The name to register under.
                    cls
                        The type to register.
                    """
                    self._entries[name] = cls

                @property
                def names(self) -> list:
                    """
                    List all registered names.

                    Returns
                    -------
                    list
                        A list of registered name strings.
                    """
                    return list(self._entries.keys())


            _default_registry = Registry()


            def register(name: str, cls: type) -> None:
                """
                Register a type in the default :py:class:`Registry`.

                Calls :py:meth:`Registry.add` on the default instance.

                Parameters
                ----------
                name
                    The name to register under.
                cls
                    The type to register.
                """
                _default_registry.add(name, cls)


            def lookup(name: str) -> type:
                """
                Look up a type in the default :py:class:`Registry`.

                Delegates to :py:meth:`Registry.get`. May raise
                :py:exc:`KeyError` in strict mode.

                Parameters
                ----------
                name
                    The name to look up.

                Returns
                -------
                type
                    The registered type.
                """
                return _default_registry.get(name)


            def validate_entry(entry: dict) -> bool:
                """
                Validate a registry entry dict.

                An entry must have ``"name"`` and ``"cls"`` keys. The ``"cls"``
                value should be passable to :py:func:`register`. If invalid,
                raises :py:exc:`ValueError`.

                Checks :py:attr:`Registry.strict` on the default registry
                to determine validation level.

                Parameters
                ----------
                entry
                    A dict with ``"name"`` and ``"cls"`` keys.

                Returns
                -------
                bool
                    True if the entry is valid.

                Raises
                ------
                ValueError
                    If the entry dict is missing required keys.
                """
                if "name" not in entry or "cls" not in entry:
                    raise ValueError("Entry must have 'name' and 'cls' keys")
                return True
        ''',
        "README.md": """\
            # gdtest-v2-sphinx-mixed-roles

            A synthetic test package testing mixed Sphinx cross-reference roles.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sphinx-mixed-roles",
        "detected_module": "gdtest_sphinx_mixed_roles",
        "detected_parser": "numpy",
        "export_names": ["Registry", "register", "lookup", "validate_entry"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
