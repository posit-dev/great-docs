"""
gdtest_namespace — Implicit namespace package (no __init__.py at top).

Dimensions: A12, B1, C1, D1, E6, F6, G1, H7
Focus: Package that uses implicit namespace packaging — the top-level
       directory has no __init__.py. Tests graceful handling.
"""

SPEC = {
    "name": "gdtest_namespace",
    "description": "Implicit namespace package",
    "dimensions": ["A12", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-namespace",
            "version": "0.1.0",
            "description": "Test namespace package handling",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
        "tool": {
            "setuptools": {
                "packages": ["gdtest_namespace", "gdtest_namespace.sub"],
            },
        },
    },
    "files": {
        "gdtest_namespace/__init__.py": '''\
            """Namespace package top level."""

            __version__ = "0.1.0"
            __all__ = ["greet", "farewell"]


            def greet(name: str) -> str:
                """
                Greet someone.

                Parameters
                ----------
                name
                    The name.

                Returns
                -------
                str
                    Greeting.
                """
                return f"Hello, {name}"


            def farewell(name: str) -> str:
                """
                Say farewell.

                Parameters
                ----------
                name
                    The name.

                Returns
                -------
                str
                    Farewell message.
                """
                return f"Goodbye, {name}"
        ''',
        "gdtest_namespace/sub/__init__.py": '''\
            """Sub-namespace module."""

            def helper() -> str:
                """Return a helper string."""
                return "I help"
        ''',
        "README.md": """\
            # gdtest-namespace

            Tests namespace package handling.
        """,
    },
    "expected": {
        "detected_name": "gdtest-namespace",
        "detected_module": "gdtest_namespace",
        "detected_parser": "numpy",
        "export_names": ["greet", "farewell"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
