"""
gdtest_display_name — Tests display_name: 'My Pretty Library' config.

Dimensions: K12
Focus: display_name config option set to a custom display name.
"""

SPEC = {
    "name": "gdtest_display_name",
    "description": "Tests display_name: My Pretty Library config",
    "dimensions": ["K12"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-display-name",
            "version": "0.1.0",
            "description": "Test display_name config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "My Pretty Library",
    },
    "files": {
        "gdtest_display_name/__init__.py": '''\
            """Package testing display_name config."""

            __version__ = "0.1.0"
            __all__ = ["init", "cleanup"]


            def init(config: dict) -> None:
                """
                Initialize the library with the given configuration.

                Parameters
                ----------
                config
                    A dictionary of configuration options.

                Returns
                -------
                None
                """
                pass


            def cleanup() -> None:
                """
                Clean up all resources held by the library.

                Returns
                -------
                None
                """
                pass
        ''',
        "README.md": """\
            # gdtest-v2-display-name

            Tests display_name: My Pretty Library config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-display-name",
        "detected_module": "gdtest_display_name",
        "detected_parser": "numpy",
        "export_names": ["cleanup", "init"],
        "num_exports": 2,
    },
}
