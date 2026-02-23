"""
gdtest_ug_single_page — Single-page user guide.

Dimensions: M10
Focus: User guide with only a single .qmd page.
"""

SPEC = {
    "name": "gdtest_ug_single_page",
    "description": "Single-page user guide with just one .qmd file.",
    "dimensions": ["M10"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-single-page",
            "version": "0.1.0",
            "description": "Test single-page user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_single_page/__init__.py": '"""Test package for single-page user guide."""\n',
        "gdtest_ug_single_page/core.py": '''
            """Core hello/goodbye functions."""


            def hello(name: str) -> str:
                """Greet someone by name.

                Parameters
                ----------
                name : str
                    The name of the person to greet.

                Returns
                -------
                str
                    A greeting message.

                Examples
                --------
                >>> hello("World")
                'Hello, World!'
                """
                return f"Hello, {name}!"


            def goodbye() -> None:
                """Say goodbye and clean up.

                Returns
                -------
                None

                Examples
                --------
                >>> goodbye()
                """
                pass
        ''',
        "user_guide/getting-started.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "Everything you need to know in a single page.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/getting-started.html",
        ],
        "files_contain": {
            "great-docs/user-guide/getting-started.html": [
                "Getting Started",
                "single page",
            ],
        },
    },
}
