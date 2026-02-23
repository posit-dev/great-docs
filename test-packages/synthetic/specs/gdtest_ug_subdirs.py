"""
gdtest_ug_subdirs — User guide with subdirectory organization.

Dimensions: M4
Focus: User guide pages organized into subdirectories within user_guide/.
"""

SPEC = {
    "name": "gdtest_ug_subdirs",
    "description": "User guide with subdirectories for organizing pages into groups.",
    "dimensions": ["M4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-subdirs",
            "version": "0.1.0",
            "description": "Test user guide with subdirectory organization.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_subdirs/__init__.py": '"""Test package for user guide with subdirectories."""\n',
        "gdtest_ug_subdirs/core.py": '''
            """Core configure/reset functions."""


            def configure(opts: dict) -> None:
                """Configure the application with the given options.

                Parameters
                ----------
                opts : dict
                    A dictionary of configuration options.

                Examples
                --------
                >>> configure({"debug": True})
                """
                pass


            def reset() -> None:
                """Reset all configuration to defaults.

                Returns
                -------
                None

                Examples
                --------
                >>> reset()
                """
                pass
        ''',
        "user_guide/basics/01-intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "An introduction to the basics of the library.\n"
        ),
        "user_guide/basics/02-setup.qmd": (
            "---\ntitle: Setup\n---\n\n# Setup\n\nHow to set up your environment.\n"
        ),
        "user_guide/advanced/01-customization.qmd": (
            "---\n"
            "title: Customization\n"
            "---\n"
            "\n"
            "# Customization\n"
            "\n"
            "Customize the library to fit your workflow.\n"
        ),
        "user_guide/advanced/02-plugins.qmd": (
            "---\ntitle: Plugins\n---\n\n# Plugins\n\nExtend functionality with plugins.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/basics/01-intro.html",
            "great-docs/user-guide/basics/02-setup.html",
            "great-docs/user-guide/advanced/01-customization.html",
            "great-docs/user-guide/advanced/02-plugins.html",
        ],
        "files_contain": {
            "great-docs/user-guide/basics/01-intro.html": ["Introduction", "basics"],
            "great-docs/user-guide/basics/02-setup.html": ["Setup", "environment"],
            "great-docs/user-guide/advanced/01-customization.html": ["Customization"],
            "great-docs/user-guide/advanced/02-plugins.html": ["Plugins"],
        },
    },
}
