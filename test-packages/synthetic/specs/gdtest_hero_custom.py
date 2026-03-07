"""
gdtest_hero_custom — Hero with custom name, tagline, logo_height, and badges
suppressed.

Dimensions: K13
Focus: Tests that individual hero sub-options override the defaults:
       custom name (instead of display_name), custom tagline (instead
       of pyproject description), custom logo_height, and badges: false.
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#198754"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_custom",
    "description": "Hero with custom name, tagline, height, and no badges",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-custom",
            "version": "0.3.0",
            "description": "Default description that should be overridden",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Default Display Name",
        "logo": "assets/logo.svg",
        "hero": {
            "name": "Custom Hero Name",
            "tagline": "A completely custom tagline for the hero",
            "logo_height": "120px",
            "badges": False,
        },
    },
    "files": {
        "gdtest_hero_custom/__init__.py": '''\
            """A package with custom hero settings."""

            __version__ = "0.3.0"
            __all__ = ["transform"]


            def transform(value: int) -> int:
                """
                Transform an integer value.

                Parameters
                ----------
                value
                    The input value.

                Returns
                -------
                int
                    The transformed value.
                """
                return value * 2
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "README.md": """\
            # gdtest-hero-custom

            [![PyPI](https://img.shields.io/badge/pypi-v0.3.0-blue)](https://pypi.org/p/gdtest-hero-custom/)
            [![License](https://img.shields.io/badge/license-MIT-green)](https://opensource.org/licenses/MIT)

            Default description that should be overridden.

            ## Features

            - Custom hero settings
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-custom",
        "detected_module": "gdtest_hero_custom",
        "detected_parser": "numpy",
        "export_names": ["transform"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
