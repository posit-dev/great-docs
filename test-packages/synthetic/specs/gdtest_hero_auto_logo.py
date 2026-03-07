"""
gdtest_hero_auto_logo — Auto-detect hero logo files from conventional paths.

Dimensions: K13
Focus: Tests that placing ``logo-hero.svg`` and ``logo-hero-dark.svg`` in the
       ``assets/`` directory causes the hero section to auto-enable and use
       those files, without any explicit ``hero.logo`` configuration.
       The navbar uses the regular ``logo.svg``; the hero should use
       ``logo-hero.svg`` / ``logo-hero-dark.svg``.
"""

_NAVBAR_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect width="32" height="32" rx="6" fill="#2780e3"/>
  <text x="16" y="22" text-anchor="middle" fill="#fff" font-size="16" font-weight="bold">NB</text>
</svg>
"""

_HERO_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 50" width="200" height="50">
  <rect width="200" height="50" rx="8" fill="#2780e3"/>
  <text x="100" y="33" text-anchor="middle" fill="#fff" font-size="20" font-weight="bold">Hero Logo</text>
</svg>
"""

_HERO_LOGO_DARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 50" width="200" height="50">
  <rect width="200" height="50" rx="8" fill="#4da3ff"/>
  <text x="100" y="33" text-anchor="middle" fill="#fff" font-size="20" font-weight="bold">Hero Logo</text>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_auto_logo",
    "description": "Auto-detect hero logo files from assets/logo-hero.svg",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-auto-logo",
            "version": "0.1.0",
            "description": "A package with auto-detected hero logo files",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero Auto Logo",
        "logo": "assets/logo.svg",
    },
    "files": {
        "gdtest_hero_auto_logo/__init__.py": '''\
            """A package with auto-detected hero logo files."""

            __version__ = "0.1.0"
            __all__ = ["transform"]


            def transform(data: str) -> str:
                """
                Transform input data.

                Parameters
                ----------
                data
                    The data to transform.

                Returns
                -------
                str
                    The transformed data.
                """
                return data
        ''',
        "assets/logo.svg": _NAVBAR_LOGO_SVG,
        "assets/logo-hero.svg": _HERO_LOGO_SVG,
        "assets/logo-hero-dark.svg": _HERO_LOGO_DARK_SVG,
        "README.md": """\
            # gdtest-hero-auto-logo

            A package with auto-detected hero logo files.

            ## Features

            - Transforms data
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-auto-logo",
        "detected_module": "gdtest_hero_auto_logo",
        "detected_parser": "numpy",
        "export_names": ["transform"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
