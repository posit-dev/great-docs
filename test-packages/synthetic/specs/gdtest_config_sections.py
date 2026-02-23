"""
gdtest_config_sections — Tests sections config for custom page groups.

Dimensions: K18
Focus: sections config option with a custom section directory.
"""

SPEC = {
    "name": "gdtest_config_sections",
    "description": "Tests sections config for custom page groups",
    "dimensions": ["K18"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-sections",
            "version": "0.1.0",
            "description": "Test sections config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Examples", "dir": "examples"},
        ],
    },
    "files": {
        "gdtest_config_sections/__init__.py": '''\
            """Package testing sections config."""

            __version__ = "0.1.0"
            __all__ = ["transform", "validate"]


            def transform(data: list) -> list:
                """
                Transform a list of data items.

                Parameters
                ----------
                data
                    The input data to transform.

                Returns
                -------
                list
                    The transformed data.
                """
                return data


            def validate(data: list) -> bool:
                """
                Validate a list of data items.

                Parameters
                ----------
                data
                    The input data to validate.

                Returns
                -------
                bool
                    True if the data is valid.
                """
                return True
        ''',
        "examples/basic-usage.qmd": """\
            ---
            title: Basic Usage
            ---

            ## Getting Started

            This example shows basic usage of the library.
        """,
        "examples/advanced-patterns.qmd": """\
            ---
            title: Advanced Patterns
            ---

            ## Advanced Usage

            This example demonstrates advanced patterns.
        """,
        "README.md": """\
            # gdtest-v2-config-sections

            Tests sections config for custom page groups.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-config-sections",
        "detected_module": "gdtest_config_sections",
        "detected_parser": "numpy",
        "export_names": ["transform", "validate"],
        "num_exports": 2,
    },
}
