"""
gdtest_hero_no_name — Hero with name suppressed (``hero.name: false``) and a
hero-specific logo override.

Dimensions: K13
Focus: Regression coverage for issue #218. When ``hero.name: false`` is set,
       the hero name must be suppressed entirely rather than falling back to
       the package / display name. The hero also overrides the navbar logo
       with its own image, so the rendered hero shows the wordmark logo and
       NO name text (no ``gd-hero-name`` element).
"""

_LETTERMARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect width="32" height="32" rx="6" fill="#fd7e14"/>
  <text x="16" y="22" text-anchor="middle" fill="#fff" font-size="16" font-weight="bold">NN</text>
</svg>
"""

_HERO_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 60" width="240" height="60">
  <rect width="240" height="60" rx="8" fill="#fd7e14"/>
  <text x="120" y="38" text-anchor="middle" fill="#fff" font-size="22" font-weight="bold">NoName</text>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_no_name",
    "description": "Hero with name suppressed (hero.name: false) plus a logo override",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-no-name",
            "version": "0.2.0",
            "description": "A package whose hero name is suppressed",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero No Name",
        "logo": "assets/lettermark.svg",
        "hero": {
            "name": False,
            "logo": "assets/hero-logo.svg",
            "logo_height": "120px",
        },
    },
    "files": {
        "gdtest_hero_no_name/__init__.py": '''\
            """A package whose hero suppresses the name."""

            __version__ = "0.2.0"
            __all__ = ["convert"]


            def convert(value: str) -> str:
                """
                Convert a value to its canonical form.

                Parameters
                ----------
                value
                    The value to convert.

                Returns
                -------
                str
                    The converted value.
                """
                return value.strip().lower()
        ''',
        "assets/lettermark.svg": _LETTERMARK_SVG,
        "assets/hero-logo.svg": _HERO_LOGO_SVG,
        "README.md": """\
            # gdtest-hero-no-name

            [![PyPI](https://img.shields.io/badge/pypi-v0.2.0-blue)](https://pypi.org/p/gdtest-hero-no-name/)

            A package whose hero name is suppressed.

            ## Features

            - Suppressed hero name
            - Hero-specific logo override
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-no-name",
        "detected_module": "gdtest_hero_no_name",
        "detected_parser": "numpy",
        "export_names": ["convert"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
