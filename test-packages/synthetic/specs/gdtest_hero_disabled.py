"""
gdtest_hero_disabled — Hero section explicitly disabled via ``hero: false``.

Dimensions: K13
Focus: Tests that setting ``hero: false`` in great-docs.yml prevents
       the hero section from appearing on the landing page, even when
       a logo is configured (which would normally auto-enable it).
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#6c757d"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_disabled",
    "description": "Hero section disabled despite logo being configured",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-disabled",
            "version": "0.1.0",
            "description": "A package demonstrating hero: false",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero Disabled",
        "logo": "assets/logo.svg",
        "hero": False,
    },
    "files": {
        "gdtest_hero_disabled/__init__.py": '''\
            """A package with hero disabled."""

            __version__ = "0.1.0"
            __all__ = ["noop"]


            def noop() -> None:
                """
                Do nothing.

                Returns
                -------
                None
                """
                pass
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "README.md": """\
            # gdtest-hero-disabled

            [![PyPI](https://img.shields.io/badge/pypi-v0.1.0-blue)](https://pypi.org/p/gdtest-hero-disabled/)

            A package demonstrating hero: false.

            ## Features

            - Hero is disabled
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-disabled",
        "detected_module": "gdtest_hero_disabled",
        "detected_parser": "numpy",
        "export_names": ["noop"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
