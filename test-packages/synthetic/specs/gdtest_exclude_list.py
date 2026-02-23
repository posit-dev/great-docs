"""
gdtest_exclude_list — Tests exclude config.

Dimensions: K16
Focus: exclude config option to hide specific symbols from the API reference.
"""

SPEC = {
    "name": "gdtest_exclude_list",
    "description": "Tests exclude config",
    "dimensions": ["K16"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-exclude-list",
            "version": "0.1.0",
            "description": "Test exclude config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "exclude": ["_hidden_func", "InternalHelper"],
    },
    "files": {
        "gdtest_exclude_list/__init__.py": '''\
            """Package testing exclude config."""

            __version__ = "0.1.0"
            __all__ = ["public_a", "public_b", "public_c", "_hidden_func", "InternalHelper"]


            def public_a() -> str:
                """
                Return public value A.

                Returns
                -------
                str
                    The string value A.
                """
                return "a"


            def public_b() -> str:
                """
                Return public value B.

                Returns
                -------
                str
                    The string value B.
                """
                return "b"


            def public_c() -> str:
                """
                Return public value C.

                Returns
                -------
                str
                    The string value C.
                """
                return "c"


            def _hidden_func() -> str:
                """
                A hidden function that should be excluded.

                Returns
                -------
                str
                    A hidden value.
                """
                return "hidden"


            class InternalHelper:
                """An internal helper class that should be excluded."""

                def help(self) -> str:
                    """
                    Provide help.

                    Returns
                    -------
                    str
                        A help message.
                    """
                    return "help"
        ''',
        "README.md": """\
            # gdtest-v2-exclude-list

            Tests exclude config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-exclude-list",
        "detected_module": "gdtest_exclude_list",
        "detected_parser": "numpy",
        "export_names": ["public_a", "public_b", "public_c"],
        "num_exports": 3,
    },
}
