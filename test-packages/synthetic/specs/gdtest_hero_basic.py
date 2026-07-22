"""
gdtest_hero_basic — Hero section with logo, name, tagline, and top-of-file badges.

Dimensions: K13
Focus: Tests that providing a logo config auto-enables the hero section
       on the landing page, displaying the logo, package name, tagline,
       and badges extracted from the top of the README.
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#2780e3"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_basic",
    "description": "Hero section with logo, name, tagline, and badges",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-basic",
            "version": "0.1.0",
            "description": "A test package for hero section rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero Basic",
        "logo": "assets/logo.svg",
    },
    "files": {
        "gdtest_hero_basic/__init__.py": '''\
            """A test package for hero section rendering."""

            __version__ = "0.1.0"
            __all__ = ["greet"]


            def greet(name: str) -> str:
                """
                Greet someone by name.

                Parameters
                ----------
                name
                    The name of the person to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "README.md": """\
            # gdtest-hero-basic

            [![PyPI version](https://img.shields.io/badge/pypi-v0.1.0-blue.svg)](https://pypi.org/p/gdtest-hero-basic/)
            [![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)

            A test package for hero section rendering.

            ## Features

            - Simple API
            - Well documented
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-basic",
        "detected_module": "gdtest_hero_basic",
        "detected_parser": "numpy",
        "export_names": ["greet"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
