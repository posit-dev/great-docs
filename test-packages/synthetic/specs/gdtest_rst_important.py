"""
gdtest_rst_important — Tests .. important:: directives in docstrings.

Dimensions: L8
Focus: RST important directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_important",
    "description": "Tests important RST directives in docstrings",
    "dimensions": ["L8"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-important",
            "version": "0.1.0",
            "description": "Test important RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_important/__init__.py": '''\
            """Package testing important RST directives."""

            __version__ = "0.1.0"
            __all__ = ["initialize", "finalize"]


            def initialize(config_path: str) -> None:
                """
                Initialize the system from a configuration file.

                Parameters
                ----------
                config_path
                    The path to the configuration file.

                Returns
                -------
                None

                .. important::
                    Must be called before any other function.
                """
                pass


            def finalize() -> None:
                """
                Finalize the system and flush pending operations.

                Returns
                -------
                None

                .. important::
                    Call this to flush all pending operations.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-v2-rst-important

            Tests important RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-important",
        "detected_module": "gdtest_rst_important",
        "detected_parser": "numpy",
        "export_names": ["finalize", "initialize"],
        "num_exports": 2,
    },
}
