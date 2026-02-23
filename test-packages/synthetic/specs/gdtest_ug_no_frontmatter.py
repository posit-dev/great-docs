"""
gdtest_ug_no_frontmatter — User guide .qmd files with no YAML frontmatter.

Dimensions: M11
Focus: User guide pages without frontmatter; title inferred from first heading.
"""

SPEC = {
    "name": "gdtest_ug_no_frontmatter",
    "description": "User guide .qmd files with no YAML frontmatter; title inferred from first heading.",
    "dimensions": ["M11"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-no-frontmatter",
            "version": "0.1.0",
            "description": "Test user guide pages without frontmatter.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_no_frontmatter/__init__.py": '"""Test package for user guide without frontmatter."""\n',
        "gdtest_ug_no_frontmatter/core.py": '''
            """Core greet/farewell functions."""


            def greet(name: str) -> str:
                """Greet a person by name.

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
                >>> greet("Alice")
                'Hello, Alice!'
                """
                return f"Hello, {name}!"


            def farewell() -> None:
                """Say farewell.

                Returns
                -------
                None

                Examples
                --------
                >>> farewell()
                """
                pass
        ''',
        "user_guide/intro.qmd": ("# Introduction\n\nWelcome to the project.\n"),
        "user_guide/usage.qmd": ("# Usage Guide\n\nHow to use.\n"),
        "README.md": (
            "# gdtest-v2-ug-no-frontmatter\n\nTest user guide pages without YAML frontmatter.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/intro.html",
            "great-docs/user-guide/usage.html",
        ],
        "files_contain": {
            "great-docs/user-guide/intro.html": ["Introduction", "Welcome to the project"],
            "great-docs/user-guide/usage.html": ["Usage Guide", "How to use"],
        },
    },
}
