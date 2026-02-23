"""
gdtest_sidebar_disabled — Tests sidebar_filter.enabled: false config.

Dimensions: K6
Focus: sidebar_filter.enabled config option set to false to disable sidebar filtering.
"""

SPEC = {
    "name": "gdtest_sidebar_disabled",
    "description": "Tests sidebar_filter.enabled: false config",
    "dimensions": ["K6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sidebar-disabled",
            "version": "0.1.0",
            "description": "Test sidebar_filter.enabled false config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sidebar_filter": {
            "enabled": False,
        },
    },
    "files": {
        "gdtest_sidebar_disabled/__init__.py": '''\
            """Package testing sidebar_filter.enabled false config."""

            __version__ = "0.1.0"
            __all__ = ["func_a", "func_b", "func_c", "func_d", "func_e"]


            def func_a() -> int:
                """
                Return the value A.

                Returns
                -------
                int
                    The integer value A.
                """
                return 1


            def func_b() -> int:
                """
                Return the value B.

                Returns
                -------
                int
                    The integer value B.
                """
                return 2


            def func_c() -> int:
                """
                Return the value C.

                Returns
                -------
                int
                    The integer value C.
                """
                return 3


            def func_d() -> int:
                """
                Return the value D.

                Returns
                -------
                int
                    The integer value D.
                """
                return 4


            def func_e() -> int:
                """
                Return the value E.

                Returns
                -------
                int
                    The integer value E.
                """
                return 5
        ''',
        "README.md": """\
            # gdtest-v2-sidebar-disabled

            Tests sidebar_filter.enabled: false config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sidebar-disabled",
        "detected_module": "gdtest_sidebar_disabled",
        "detected_parser": "numpy",
        "export_names": ["func_a", "func_b", "func_c", "func_d", "func_e"],
        "num_exports": 5,
    },
}
