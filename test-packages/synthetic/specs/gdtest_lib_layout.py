"""
gdtest_lib_layout — lib/ layout convention.

Dimensions: A4, B1, C1, D1, E6, F6, G1, H7
Focus: Package code lives under lib/<pkg>/.
       Tests _find_package_init detection of lib/ directory.
"""

SPEC = {
    "name": "gdtest_lib_layout",
    "description": "lib/ layout convention",
    "dimensions": ["A4", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-lib-layout",
            "version": "0.1.0",
            "description": "A synthetic test package using lib/ layout",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "lib/gdtest_lib_layout/__init__.py": '''\
            """A test package using the lib/ layout convention."""

            __version__ = "0.1.0"
            __all__ = ["open_connection", "close_connection"]


            def open_connection(url: str) -> bool:
                """
                Open a connection to the given URL.

                Parameters
                ----------
                url
                    The URL to connect to.

                Returns
                -------
                bool
                    True if connected successfully.
                """
                return True


            def close_connection() -> None:
                """
                Close the current connection.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-lib-layout

            A synthetic test package using the ``lib/`` layout convention.
        """,
    },
    "expected": {
        "detected_name": "gdtest-lib-layout",
        "detected_module": "gdtest_lib_layout",
        "detected_parser": "numpy",
        "export_names": ["open_connection", "close_connection"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp'],
},
}
