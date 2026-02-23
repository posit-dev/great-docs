"""
gdtest_ug_combo — Complex user guide combining numbered files, sections, subdirs, and mixed extensions.

Dimensions: M2, M3, M4, M7
Focus: User guide with numbered files, guide-section frontmatter, subdirectories, and mixed .qmd/.md extensions.
"""

SPEC = {
    "name": "gdtest_ug_combo",
    "description": "Complex user guide combining numbered files, frontmatter sections, subdirs, and mixed extensions.",
    "dimensions": ["M2", "M3", "M4", "M7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-combo",
            "version": "0.1.0",
            "description": "Test complex user guide combination.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_combo/__init__.py": '"""Test package for complex user guide combo."""\n',
        "gdtest_ug_combo/core.py": '''
            """Core build/deploy functions."""


            def build(config: dict) -> None:
                """Build the project with the given configuration.

                Parameters
                ----------
                config : dict
                    A dictionary of build configuration options.

                Returns
                -------
                None

                Examples
                --------
                >>> build({"target": "production"})
                """
                pass


            def deploy(target: str) -> str:
                """Deploy the project to the specified target.

                Parameters
                ----------
                target : str
                    The deployment target name.

                Returns
                -------
                str
                    A status message indicating the result of the deployment.

                Examples
                --------
                >>> deploy("staging")
                'Deployed to staging'
                """
                return f"Deployed to {target}"
        ''',
        "user_guide/basics/01-intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "guide-section: Basics\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "An introduction to the basics of the project.\n"
        ),
        "user_guide/basics/02-install.md": (
            "---\n"
            "title: Installation\n"
            "guide-section: Basics\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "How to install the project using pip.\n"
        ),
        "user_guide/advanced/01-config.qmd": (
            "---\n"
            "title: Configuration\n"
            "guide-section: Advanced\n"
            "---\n"
            "\n"
            "# Configuration\n"
            "\n"
            "Advanced configuration options for the project.\n"
        ),
        "user_guide/advanced/02-extend.qmd": (
            "---\n"
            "title: Extending\n"
            "guide-section: Advanced\n"
            "---\n"
            "\n"
            "# Extending\n"
            "\n"
            "How to extend the project with custom plugins.\n"
        ),
        "README.md": (
            "# gdtest-v2-ug-combo\n"
            "\n"
            "Complex user guide combining numbered files, sections, subdirs, and mixed extensions.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/basics/01-intro.html",
            "great-docs/user-guide/basics/02-install.html",
            "great-docs/user-guide/advanced/01-config.html",
            "great-docs/user-guide/advanced/02-extend.html",
        ],
        "files_contain": {
            "great-docs/user-guide/basics/01-intro.html": ["Introduction", "basics"],
            "great-docs/user-guide/basics/02-install.html": ["Installation", "pip"],
            "great-docs/user-guide/advanced/01-config.html": ["Configuration", "Advanced"],
            "great-docs/user-guide/advanced/02-extend.html": ["Extending", "plugins"],
        },
    },
}
