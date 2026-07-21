"""
gdtest_hero_readme_badges — Hero section from a README with centered-div badges.

Dimensions: K13
Focus: Tests that a README using the ``<div align="center">`` pattern
       (common in repos like Pointblank, Great Tables) has its badges
       extracted into the hero section and the centered div stripped from
       the landing page body.
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#e35027"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_readme_badges",
    "description": "Hero section from README with centered-div badges",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-readme-badges",
            "version": "0.2.0",
            "description": "A package with Pointblank-style centered README badges",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero Badges",
        "logo": "assets/logo.svg",
    },
    "files": {
        "gdtest_hero_readme_badges/__init__.py": '''\
            """A test package for centered-div badge extraction."""

            __version__ = "0.2.0"
            __all__ = ["validate"]


            def validate(data: dict) -> bool:
                """
                Validate a data dictionary.

                Parameters
                ----------
                data
                    The data to validate.

                Returns
                -------
                bool
                    True if valid.
                """
                return bool(data)
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "README.md": (
            "# gdtest-hero-readme-badges\n"
            "\n"
            '<div align="center">\n'
            '<img src="https://example.com/hero-image.png" width="350">\n'
            "<br />\n"
            "*A package with centered-div badge extraction*\n"
            "<br />\n"
            "[![PyPI](https://img.shields.io/badge/pypi-v0.2.0-blue)](https://pypi.org/p/gdtest-hero-readme-badges/)\n"
            "[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/ci)\n"
            "[![Coverage](https://codecov.io/gh/example/badge.svg)](https://codecov.io/gh/example)\n"
            "</div>\n"
            "\n"
            "## Overview\n"
            "\n"
            "This package demonstrates the centered-div badge extraction pattern.\n"
            "\n"
            "## Features\n"
            "\n"
            "- Validates data dictionaries\n"
            "- Simple and fast\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-hero-readme-badges",
        "detected_module": "gdtest_hero_readme_badges",
        "detected_parser": "numpy",
        "export_names": ["validate"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
