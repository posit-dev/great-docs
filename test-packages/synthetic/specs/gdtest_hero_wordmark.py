"""
gdtest_hero_wordmark — Separate hero wordmark logo (light/dark) from navbar
lettermark.

Dimensions: K13
Focus: Tests that ``hero.logo`` can specify a different image (with
       light/dark variants) from the top-level ``logo`` used in the
       navbar.  The navbar should use the lettermark; the hero section
       should use the wordmark.
"""

_LETTERMARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect width="32" height="32" rx="6" fill="#2780e3"/>
  <text x="16" y="22" text-anchor="middle" fill="#fff" font-size="16" font-weight="bold">LM</text>
</svg>
"""

_LETTERMARK_DARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect width="32" height="32" rx="6" fill="#4da3ff"/>
  <text x="16" y="22" text-anchor="middle" fill="#fff" font-size="16" font-weight="bold">LM</text>
</svg>
"""

_WORDMARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 50" width="200" height="50">
  <rect width="200" height="50" rx="8" fill="#2780e3"/>
  <text x="100" y="33" text-anchor="middle" fill="#fff" font-size="20" font-weight="bold">Wordmark</text>
</svg>
"""

_WORDMARK_DARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 50" width="200" height="50">
  <rect width="200" height="50" rx="8" fill="#4da3ff"/>
  <text x="100" y="33" text-anchor="middle" fill="#fff" font-size="20" font-weight="bold">Wordmark</text>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_wordmark",
    "description": "Separate hero wordmark logo from navbar lettermark",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-wordmark",
            "version": "0.1.0",
            "description": "A package with separate hero and navbar logos",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero Wordmark",
        "logo": {
            "light": "assets/lettermark.svg",
            "dark": "assets/lettermark-dark.svg",
        },
        "hero": {
            "logo": {
                "light": "assets/wordmark.svg",
                "dark": "assets/wordmark-dark.svg",
            },
            "logo_height": "100px",
        },
    },
    "files": {
        "gdtest_hero_wordmark/__init__.py": '''\
            """A package with separate hero and navbar logos."""

            __version__ = "0.1.0"
            __all__ = ["render"]


            def render(template: str) -> str:
                """
                Render a template string.

                Parameters
                ----------
                template
                    The template to render.

                Returns
                -------
                str
                    The rendered output.
                """
                return template
        ''',
        "assets/lettermark.svg": _LETTERMARK_SVG,
        "assets/lettermark-dark.svg": _LETTERMARK_DARK_SVG,
        "assets/wordmark.svg": _WORDMARK_SVG,
        "assets/wordmark-dark.svg": _WORDMARK_DARK_SVG,
        "README.md": """\
            # gdtest-hero-wordmark

            A package with separate hero and navbar logos.

            ## Features

            - Renders templates
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-wordmark",
        "detected_module": "gdtest_hero_wordmark",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
