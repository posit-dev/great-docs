"""
gdtest_ug_custom_dir — User guide in a custom directory via config.

Dimensions: M5
Focus: User guide sourced from docs/ instead of user_guide/ using config.
"""

SPEC = {
    "name": "gdtest_ug_custom_dir",
    "description": "User guide in docs/ directory instead of user_guide/ via config.",
    "dimensions": ["M5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-custom-dir",
            "version": "0.1.0",
            "description": "Test user guide in custom directory.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": "docs",
    },
    "files": {
        "gdtest_ug_custom_dir/__init__.py": '"""Test package for custom user guide directory."""\n',
        "gdtest_ug_custom_dir/core.py": '''
            """Core load/save functions."""


            def load(path: str) -> dict:
                """Load data from the given file path.

                Parameters
                ----------
                path : str
                    The path to load data from.

                Returns
                -------
                dict
                    The loaded data as a dictionary.

                Examples
                --------
                >>> load("config.json")
                {'key': 'value'}
                """
                return {}


            def save(data: dict) -> None:
                """Save data to persistent storage.

                Parameters
                ----------
                data : dict
                    The data to save.

                Examples
                --------
                >>> save({"key": "value"})
                """
                pass
        ''',
        "docs/getting-started.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "A guide to getting started with the library.\n"
        ),
        "docs/reference-guide.qmd": (
            "---\n"
            "title: Reference Guide\n"
            "---\n"
            "\n"
            "# Reference Guide\n"
            "\n"
            "A comprehensive reference guide for all features.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/getting-started.html",
            "great-docs/user-guide/reference-guide.html",
        ],
        "files_contain": {
            "great-docs/user-guide/getting-started.html": ["Getting Started"],
            "great-docs/user-guide/reference-guide.html": ["Reference Guide"],
        },
    },
}
