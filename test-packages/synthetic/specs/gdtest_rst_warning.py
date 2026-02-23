"""
gdtest_rst_warning — Tests .. warning:: directives in docstrings.

Dimensions: L4
Focus: RST warning directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_warning",
    "description": "Tests warning RST directives in docstrings",
    "dimensions": ["L4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-warning",
            "version": "0.1.0",
            "description": "Test warning RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_warning/__init__.py": '''\
            """Package testing warning RST directives."""

            __version__ = "0.1.0"
            __all__ = ["delete_all", "force_restart"]


            def delete_all(confirm: bool = False) -> int:
                """
                Delete all records from the store.

                Parameters
                ----------
                confirm
                    Must be True to proceed with deletion.

                Returns
                -------
                int
                    The number of records deleted.

                .. warning::
                    This operation cannot be undone.
                """
                return 0


            def force_restart() -> None:
                """
                Force an immediate restart of the service.

                Returns
                -------
                None

                .. warning::
                    All unsaved data will be lost.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-v2-rst-warning

            Tests warning RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-warning",
        "detected_module": "gdtest_rst_warning",
        "detected_parser": "numpy",
        "export_names": ["delete_all", "force_restart"],
        "num_exports": 2,
    },
}
