"""
gdtest_sidebar_min_items — Tests sidebar_filter.min_items: 3 config.

Dimensions: K7
Focus: sidebar_filter.min_items config option set to 3.
"""

SPEC = {
    "name": "gdtest_sidebar_min_items",
    "description": "Tests sidebar_filter.min_items: 3 config",
    "dimensions": ["K7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sidebar-min-items",
            "version": "0.1.0",
            "description": "Test sidebar_filter.min_items 3 config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sidebar_filter": {
            "min_items": 3,
        },
    },
    "files": {
        "gdtest_sidebar_min_items/__init__.py": '''\
            """Package testing sidebar_filter.min_items config."""

            __version__ = "0.1.0"
            __all__ = ["func_w", "func_x", "func_y", "func_z"]


            def func_w() -> str:
                """
                Return the value W.

                Returns
                -------
                str
                    The string value W.
                """
                return "W"


            def func_x() -> str:
                """
                Return the value X.

                Returns
                -------
                str
                    The string value X.
                """
                return "X"


            def func_y() -> str:
                """
                Return the value Y.

                Returns
                -------
                str
                    The string value Y.
                """
                return "Y"


            def func_z() -> str:
                """
                Return the value Z.

                Returns
                -------
                str
                    The string value Z.
                """
                return "Z"
        ''',
        "README.md": """\
            # gdtest-v2-sidebar-min-items

            Tests sidebar_filter.min_items: 3 config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sidebar-min-items",
        "detected_module": "gdtest_sidebar_min_items",
        "detected_parser": "numpy",
        "export_names": ["func_w", "func_x", "func_y", "func_z"],
        "num_exports": 4,
    },
}
