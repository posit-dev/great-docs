"""
gdtest_hero_index_qmd — Hero section generated from an ``index.qmd`` source
(not README.md).

Dimensions: K13
Focus: Tests that the hero section works when the landing page source is
       ``index.qmd`` rather than ``README.md``.  Badges in the ``index.qmd``
       are auto-extracted just like from a README.
"""

_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#6610f2"/>
</svg>
"""

SPEC = {
    "name": "gdtest_hero_index_qmd",
    "description": "Hero section from index.qmd source file",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hero-index-qmd",
            "version": "0.1.0",
            "description": "A package with an index.qmd landing page",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Hero Index QMD",
        "logo": "assets/logo.svg",
    },
    "files": {
        "gdtest_hero_index_qmd/__init__.py": '''\
            """A package with an index.qmd landing page."""

            __version__ = "0.1.0"
            __all__ = ["compute"]


            def compute(x: float, y: float) -> float:
                """
                Compute the sum of two values.

                Parameters
                ----------
                x
                    First value.
                y
                    Second value.

                Returns
                -------
                float
                    The sum.
                """
                return x + y
        ''',
        "assets/logo.svg": _LOGO_SVG,
        "index.qmd": """\
            # gdtest-hero-index-qmd

            [![PyPI](https://img.shields.io/badge/pypi-v0.1.0-blue)](https://pypi.org/p/gdtest-hero-index-qmd/)

            A package with an index.qmd landing page.

            ## Overview

            This tests that hero generation works from an index.qmd source.

            ## Features

            - Custom index.qmd content
            - Badge auto-extraction
        """,
    },
    "expected": {
        "detected_name": "gdtest-hero-index-qmd",
        "detected_module": "gdtest_hero_index_qmd",
        "detected_parser": "numpy",
        "export_names": ["compute"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
