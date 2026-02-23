"""
gdtest_rst_danger — Tests .. danger:: directives in docstrings.

Dimensions: L7
Focus: RST danger directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_danger",
    "description": "Tests danger RST directives in docstrings",
    "dimensions": ["L7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-danger",
            "version": "0.1.0",
            "description": "Test danger RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_danger/__init__.py": '''\
            """Package testing danger RST directives."""

            __version__ = "0.1.0"
            __all__ = ["drop_database", "purge_cache"]


            def drop_database(name: str) -> None:
                """
                Drop an entire database by name.

                Parameters
                ----------
                name
                    The name of the database to drop.

                Returns
                -------
                None

                .. danger::
                    This permanently destroys the database.
                """
                pass


            def purge_cache() -> int:
                """
                Purge all entries from the cache.

                Returns
                -------
                int
                    The number of cache entries purged.

                .. danger::
                    Cannot be reversed. All cached data is lost.
                """
                return 0
        ''',
        "README.md": """\
            # gdtest-v2-rst-danger

            Tests danger RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-danger",
        "detected_module": "gdtest_rst_danger",
        "detected_parser": "numpy",
        "export_names": ["drop_database", "purge_cache"],
        "num_exports": 2,
    },
}
