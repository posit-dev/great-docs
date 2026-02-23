"""
gdtest_source_path — Tests source.path: 'src/mylib' config.

Dimensions: K3
Focus: source.path config option set to a custom path.
"""

SPEC = {
    "name": "gdtest_source_path",
    "description": "Tests source.path: src/mylib config",
    "dimensions": ["K3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-source-path",
            "version": "0.1.0",
            "description": "Test source.path src/mylib config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "source": {
            "path": "src/mylib",
        },
    },
    "files": {
        "gdtest_source_path/__init__.py": '''\
            """Package testing source.path config."""

            __version__ = "0.1.0"
            __all__ = ["parse", "format_output"]


            def parse(text: str) -> dict:
                """
                Parse text into a dictionary.

                Parameters
                ----------
                text
                    The text to parse.

                Returns
                -------
                dict
                    The parsed result.
                """
                return {}


            def format_output(data: dict) -> str:
                """
                Format a dictionary as output text.

                Parameters
                ----------
                data
                    The data to format.

                Returns
                -------
                str
                    The formatted output.
                """
                return ""
        ''',
        "README.md": """\
            # gdtest-v2-source-path

            Tests source.path: src/mylib config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-source-path",
        "detected_module": "gdtest_source_path",
        "detected_parser": "numpy",
        "export_names": ["format_output", "parse"],
        "num_exports": 2,
    },
}
