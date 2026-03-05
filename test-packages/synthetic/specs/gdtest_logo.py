"""
gdtest_logo — Logo & favicon integration.

Dimensions: K13
Focus: Tests that providing a logo config in great-docs.yml results in
       correct _quarto.yml injection (navbar.logo, navbar.title: false,
       website.favicon) and that logo files are copied into the build
       directory.
"""

# A tiny but valid SVG for testing (32x32 blue circle)
_LOGO_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#2780e3"/>
</svg>
"""

_LOGO_DARK_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <circle cx="16" cy="16" r="14" fill="#4da3ff"/>
</svg>
"""

SPEC = {
    "name": "gdtest_logo",
    "description": "Tests logo and favicon integration in the navbar",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-logo",
            "version": "0.1.0",
            "description": "Test package for logo/favicon integration",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Logo Test",
        "logo": {
            "light": "assets/logo.svg",
            "dark": "assets/logo-dark.svg",
        },
    },
    "files": {
        "gdtest_logo/__init__.py": '''\
            """A test package for logo integration."""

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
        "assets/logo-dark.svg": _LOGO_DARK_SVG,
        "README.md": """\
            # gdtest-logo

            A test package for logo/favicon integration.
        """,
    },
    "expected": {
        "detected_name": "gdtest-logo",
        "detected_module": "gdtest_logo",
        "detected_parser": "numpy",
        "export_names": ["greet"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
    },
}
