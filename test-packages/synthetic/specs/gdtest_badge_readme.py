"""
gdtest_badge_readme — README with badges, images, and complex Markdown.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: README.md with shields.io badges, images, tables, and nested
       lists. Tests complex Markdown rendering on the landing page.
"""

SPEC = {
    "name": "gdtest_badge_readme",
    "description": "README with badges, images, and complex Markdown",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-badge-readme",
            "version": "0.1.0",
            "description": "Test complex README rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_badge_readme/__init__.py": '''\
            """Package with a badge-heavy README."""

            __version__ = "0.1.0"
            __all__ = ["greet"]


            def greet(name: str) -> str:
                """
                Greet someone.

                Parameters
                ----------
                name
                    The name.

                Returns
                -------
                str
                    Greeting.
                """
                return f"Hello, {name}!"
        ''',
        "README.md": """\
            # gdtest-badge-readme

            [![PyPI version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg)](https://pypi.org/)
            [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
            [![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
            [![CI Status](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com/)

            A test package with a complex README featuring badges, tables, and nested lists.

            ## Features

            | Feature | Status | Notes |
            |---------|--------|-------|
            | Badges | Supported | Shields.io badges |
            | Tables | Supported | Standard Markdown tables |
            | Lists | Supported | Including nested lists |

            ## Quick Start

            1. Install the package:
               ```bash
               pip install gdtest-badge-readme
               ```
            2. Import and use:
               ```python
               from gdtest_badge_readme import greet
               greet("World")
               ```

            ## Advanced Topics

            - **Topic A**
              - Sub-topic A.1
              - Sub-topic A.2
                - Detail A.2.1
            - **Topic B**
              - Sub-topic B.1

            ## Links

            - [Documentation](https://example.com/docs)
            - [Source Code](https://github.com/example/repo)
            - [Issue Tracker](https://github.com/example/repo/issues)

            ---

            *This README tests complex Markdown rendering.*
        """,
    },
    "expected": {
        "detected_name": "gdtest-badge-readme",
        "detected_module": "gdtest_badge_readme",
        "detected_parser": "numpy",
        "export_names": ["greet"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
