"""Tests user_guide as a string pointing to a custom directory."""

SPEC = {
    "name": "gdtest_config_ug_string",
    "description": "Tests user_guide config as a string pointing to a custom 'guides' directory.",
    "dimensions": ["K19"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-ug-string",
            "version": "0.1.0",
            "description": "Test package for user_guide string config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": "guides",
    },
    "files": {
        "gdtest_config_ug_string/__init__.py": '"""Test package for user_guide string config."""\n',
        "gdtest_config_ug_string/core.py": '''
            """Core I/O functions."""


            def load(path: str) -> dict:
                """Load data from a file.

                Parameters
                ----------
                path : str
                    The file path to load data from.

                Returns
                -------
                dict
                    The loaded data as a dictionary.

                Examples
                --------
                >>> load("data.json")
                {'key': 'value'}
                """
                return {}


            def save(data: dict, path: str) -> None:
                """Save data to a file.

                Parameters
                ----------
                data : dict
                    The data to save.
                path : str
                    The file path to save data to.

                Examples
                --------
                >>> save({"key": "value"}, "data.json")
                """
                pass
        ''',
        "guides/intro.qmd": (
            "---\ntitle: Introduction\n---\n\n# Introduction\n\nWelcome to the guides.\n"
        ),
        "guides/setup.qmd": ("---\ntitle: Setup\n---\n\n# Setup\n\nHow to set up the project.\n"),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/intro.html",
            "great-docs/user-guide/setup.html",
        ],
        "files_contain": {
            "great-docs/user-guide/intro.html": ["Introduction", "Welcome to the guides"],
            "great-docs/user-guide/setup.html": ["Setup", "How to set up the project"],
        },
    },
}
