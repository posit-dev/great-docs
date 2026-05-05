"""
gdtest_explicit_ref — Explicit reference config sections.

Dimensions: A1, B1, C1, D1, E1+E6, F6, G1, H7
Focus: Config with explicit ``reference:`` sections.
Tests _build_sections_from_reference_config and ``members: false`` handling.
"""

SPEC = {
    "name": "gdtest_explicit_ref",
    "description": "Explicit reference sections in great-docs.yml config",
    "dimensions": ["A1", "B1", "C1", "D1", "E1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-explicit-ref",
            "version": "0.1.0",
            "description": "A package with explicit reference config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_explicit_ref/__init__.py": '''\
            """A package with explicit reference config sections."""

            __version__ = "0.1.0"
            __all__ = ["MyClass", "helper_func", "util_a", "util_b"]


            class MyClass:
                """
                A core class.

                Parameters
                ----------
                value
                    The initial value.
                """

                def __init__(self, value: int):
                    self.value = value

                def compute(self) -> int:
                    """
                    Compute a result.

                    Returns
                    -------
                    int
                        The computed result.
                    """
                    return self.value * 2

                def reset(self) -> None:
                    """Reset to zero."""
                    self.value = 0

                def increment(self) -> None:
                    """Increment value by one."""
                    self.value += 1

                def decrement(self) -> None:
                    """Decrement value by one."""
                    self.value -= 1

                def to_string(self) -> str:
                    """
                    Convert to string.

                    Returns
                    -------
                    str
                        String representation.
                    """
                    return str(self.value)

                def clone(self) -> "MyClass":
                    """
                    Create a copy.

                    Returns
                    -------
                    MyClass
                        A new instance with the same value.
                    """
                    return MyClass(self.value)


            def helper_func(x: int) -> int:
                """
                A core helper function.

                Parameters
                ----------
                x
                    Input value.

                Returns
                -------
                int
                    Processed value.
                """
                return x + 1


            def util_a(name: str) -> str:
                """
                Utility function A.

                Parameters
                ----------
                name
                    Input name.

                Returns
                -------
                str
                    Formatted name.
                """
                return name.upper()


            def util_b(items: list) -> int:
                """
                Utility function B.

                Parameters
                ----------
                items
                    A list of items.

                Returns
                -------
                int
                    Number of items.
                """
                return len(items)
        ''',
        "README.md": """\
            # gdtest-explicit-ref

            A package with explicit reference config.
        """,
    },
    "config": {
        "reference": [
            {
                "title": "Core",
                "desc": "Core functionality",
                "contents": [
                    {"name": "MyClass", "members": False},
                    "helper_func",
                ],
            },
            {
                "title": "Utilities",
                "desc": "Helper functions",
                "contents": [
                    "util_a",
                    "util_b",
                ],
            },
        ],
    },
    "expected": {
        "detected_name": "gdtest-explicit-ref",
        "detected_module": "gdtest_explicit_ref",
        "detected_parser": "numpy",
        "export_names": ["MyClass", "helper_func", "util_a", "util_b"],
        "num_exports": 4,
        "section_titles": ["Core", "Utilities"],
        "has_user_guide": False,
        "explicit_reference": True,
        "members_false_classes": ["MyClass"],
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
