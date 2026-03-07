"""
gdtest_hero_explicit_badges — Hero with an explicit badge list instead of
auto-extraction.

Dimensions: K13
Focus: Tests that providing a list under ``hero.badges`` displays those
       explicit badges in the hero section rather than auto-extracting
       from the README.  The README contains different badges that should
       NOT appear in the hero.
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#fd7e14"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_explicit_badges",
    "description": "Hero with explicit badge list (not auto-extracted)",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-explicit-badges",
            "version": "0.2.0",
            "description": "A package with manually specified hero badges",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Explicit Badges",
        "logo": "assets/logo.svg",
        "hero": {
            "badges": [
                {
                    "alt": "Custom Badge",
                    "img": "https://img.shields.io/badge/custom-badge-purple",
                    "url": "https://example.com/custom",
                },
                {
                    "alt": "Status",
                    "img": "https://img.shields.io/badge/status-stable-brightgreen",
                },
            ],
        },
    },
    "files": {
        "gdtest_hero_explicit_badges/__init__.py": '''\
            """A package with explicit hero badges."""

            __version__ = "0.2.0"
            __all__ = ["parse"]


            def parse(text: str) -> list:
                """
                Parse text into tokens.

                Parameters
                ----------
                text
                    The text to parse.

                Returns
                -------
                list
                    A list of tokens.
                """
                return text.split()
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "README.md": """\
            # gdtest-hero-explicit-badges

            [![README Badge](https://img.shields.io/badge/readme-badge-red)](https://example.com/readme)

            A package with manually specified hero badges.

            ## Features

            - Explicit badge list
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-explicit-badges",
        "detected_module": "gdtest_hero_explicit_badges",
        "detected_parser": "numpy",
        "export_names": ["parse"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
