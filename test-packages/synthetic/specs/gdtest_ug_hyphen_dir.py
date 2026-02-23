"""
gdtest_ug_hyphen_dir — User guide in a hyphenated user-guide/ directory.

Dimensions: M13
Focus: User guide sourced from user-guide/ (hyphenated) instead of user_guide/.
"""

SPEC = {
    "name": "gdtest_ug_hyphen_dir",
    "description": "User guide in user-guide/ (hyphenated directory name).",
    "dimensions": ["M13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-hyphen-dir",
            "version": "0.1.0",
            "description": "Test user guide in hyphenated directory.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_hyphen_dir/__init__.py": '"""Test package for hyphenated user-guide directory."""\n',
        "gdtest_ug_hyphen_dir/core.py": '''
            """Core start_app/stop_app functions."""


            def start_app() -> None:
                """Start the application.

                Returns
                -------
                None

                Examples
                --------
                >>> start_app()
                """
                pass


            def stop_app() -> None:
                """Stop the application.

                Returns
                -------
                None

                Examples
                --------
                >>> stop_app()
                """
                pass
        ''',
        "user-guide/01-intro.qmd": (
            "---\ntitle: Introduction\n---\n\n# Introduction\n\nWelcome to the application guide.\n"
        ),
        "user-guide/02-setup.qmd": (
            "---\ntitle: Setup\n---\n\n# Setup\n\nHow to set up the application.\n"
        ),
        "README.md": (
            "# gdtest-v2-ug-hyphen-dir\n\nTest user guide in a hyphenated user-guide/ directory.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/01-intro.html",
            "great-docs/user-guide/02-setup.html",
        ],
        "files_contain": {
            "great-docs/user-guide/01-intro.html": ["Introduction", "application guide"],
            "great-docs/user-guide/02-setup.html": ["Setup", "set up the application"],
        },
    },
}
