"""
gdtest_hero_no_logo — Hero section with logo suppressed (``logo: false``).

Dimensions: K13
Focus: Tests that setting ``hero.logo: false`` suppresses the logo image
       in the hero while still showing name, tagline, and badges.
       The top-level logo is set (so hero would auto-enable) but the
       hero-specific logo override is ``false``.
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#dc3545"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_no_logo",
    "description": "Hero with logo suppressed but name/tagline/badges shown",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-no-logo",
            "version": "0.1.0",
            "description": "A package with a text-only hero section",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero No Logo",
        "logo": "assets/logo.svg",
        "hero": {
            "logo": False,
        },
    },
    "files": {
        "gdtest_hero_no_logo/__init__.py": '''\
            """A package with a text-only hero."""

            __version__ = "0.1.0"
            __all__ = ["check"]


            def check(value: str) -> bool:
                """
                Check if a value is valid.

                Parameters
                ----------
                value
                    The value to check.

                Returns
                -------
                bool
                    True if valid.
                """
                return bool(value)
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "README.md": """\
            # gdtest-hero-no-logo

            [![PyPI](https://img.shields.io/badge/pypi-v0.1.0-blue)](https://pypi.org/p/gdtest-hero-no-logo/)

            A package with a text-only hero section.

            ## Features

            - Text-only hero
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-no-logo",
        "detected_module": "gdtest_hero_no_logo",
        "detected_parser": "numpy",
        "export_names": ["check"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
