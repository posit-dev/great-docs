"""
gdtest_rst_caution — Tests .. caution:: directives in docstrings.

Dimensions: L6
Focus: RST caution directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_caution",
    "description": "Tests caution RST directives in docstrings",
    "dimensions": ["L6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-caution",
            "version": "0.1.0",
            "description": "Test caution RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_caution/__init__.py": '''\
            """Package testing caution RST directives."""

            __version__ = "0.1.0"
            __all__ = ["modify_schema", "migrate"]


            def modify_schema(changes: dict) -> None:
                """
                Apply schema modifications.

                Parameters
                ----------
                changes
                    A dictionary describing the schema changes.

                Returns
                -------
                None

                .. caution::
                    Schema changes may break existing data.
                """
                pass


            def migrate(version: str) -> bool:
                """
                Migrate the database to the specified version.

                Parameters
                ----------
                version
                    The target version to migrate to.

                Returns
                -------
                bool
                    True if migration was successful.

                .. caution::
                    Always back up before migrating.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-v2-rst-caution

            Tests caution RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-caution",
        "detected_module": "gdtest_rst_caution",
        "detected_parser": "numpy",
        "export_names": ["migrate", "modify_schema"],
        "num_exports": 2,
    },
}
