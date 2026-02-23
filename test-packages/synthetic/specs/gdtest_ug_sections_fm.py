"""
gdtest_ug_sections_fm — User guide with guide-section frontmatter.

Dimensions: M3
Focus: User guide pages grouped by guide-section frontmatter field.
"""

SPEC = {
    "name": "gdtest_ug_sections_fm",
    "description": "User guide with guide-section frontmatter for grouping pages into sections.",
    "dimensions": ["M3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-sections-fm",
            "version": "0.1.0",
            "description": "Test guide-section frontmatter in user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_sections_fm/__init__.py": '"""Test package for guide-section frontmatter."""\n',
        "gdtest_ug_sections_fm/core.py": '''
            """Core init/extend functions."""


            def init(path: str) -> None:
                """Initialize the application at the given path.

                Parameters
                ----------
                path : str
                    The directory path to initialize.

                Examples
                --------
                >>> init("/app")
                """
                pass


            def extend(plugin: str) -> None:
                """Extend the application with a plugin.

                Parameters
                ----------
                plugin : str
                    The name of the plugin to load.

                Examples
                --------
                >>> extend("auth")
                """
                pass
        ''',
        "user_guide/01-welcome.qmd": (
            "---\n"
            "title: Welcome\n"
            "guide-section: Getting Started\n"
            "---\n"
            "\n"
            "# Welcome\n"
            "\n"
            "Welcome to the project. This guide will help you get started.\n"
        ),
        "user_guide/02-install.qmd": (
            "---\n"
            "title: Installation\n"
            "guide-section: Getting Started\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "Follow these steps to install the package.\n"
        ),
        "user_guide/03-config.qmd": (
            "---\n"
            "title: Configuration\n"
            "guide-section: Advanced Topics\n"
            "---\n"
            "\n"
            "# Configuration\n"
            "\n"
            "Advanced configuration options for power users.\n"
        ),
        "user_guide/04-extend.qmd": (
            "---\n"
            "title: Extending\n"
            "guide-section: Advanced Topics\n"
            "---\n"
            "\n"
            "# Extending\n"
            "\n"
            "How to extend the application with plugins.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/01-welcome.html",
            "great-docs/user-guide/02-install.html",
            "great-docs/user-guide/03-config.html",
            "great-docs/user-guide/04-extend.html",
        ],
        "files_contain": {
            "great-docs/user-guide/01-welcome.html": ["Welcome", "get started"],
            "great-docs/user-guide/02-install.html": ["Installation"],
            "great-docs/user-guide/03-config.html": ["Configuration", "Advanced"],
            "great-docs/user-guide/04-extend.html": ["Extending", "plugins"],
        },
    },
}
