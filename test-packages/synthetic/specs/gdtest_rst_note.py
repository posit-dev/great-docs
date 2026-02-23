"""
gdtest_rst_note — Tests .. note:: directives in docstrings.

Dimensions: L3
Focus: RST note directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_note",
    "description": "Tests note RST directives in docstrings",
    "dimensions": ["L3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-note",
            "version": "0.1.0",
            "description": "Test note RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_note/__init__.py": '''\
            """Package testing note RST directives."""

            __version__ = "0.1.0"
            __all__ = ["configure", "reset_defaults", "get_config"]


            def configure(settings: dict) -> None:
                """
                Apply configuration settings.

                Parameters
                ----------
                settings
                    A dictionary of settings to apply.

                Returns
                -------
                None

                .. note::
                    Settings are validated before applying.
                """
                pass


            def reset_defaults() -> dict:
                """
                Reset all settings to their default values.

                Returns
                -------
                dict
                    The default settings.

                .. note::
                    This restores factory settings.
                """
                return {}


            def get_config() -> dict:
                """
                Retrieve the current configuration.

                Returns
                -------
                dict
                    The current configuration dictionary.

                .. note::
                    Returns a deep copy of the configuration.
                """
                return {}
        ''',
        "README.md": """\
            # gdtest-v2-rst-note

            Tests note RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-note",
        "detected_module": "gdtest_rst_note",
        "detected_parser": "numpy",
        "export_names": ["configure", "get_config", "reset_defaults"],
        "num_exports": 3,
    },
}
