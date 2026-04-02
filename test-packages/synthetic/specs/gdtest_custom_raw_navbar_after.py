"""
gdtest_custom_raw_navbar_after — Raw custom page inserted after User Guide.

Dimensions: N7
Focus: Raw custom HTML page, navbar placement, and coexistence with a user guide.
"""

SPEC = {
    "name": "gdtest_custom_raw_navbar_after",
    "description": "Raw custom page inserted after the User Guide navbar item.",
    "dimensions": ["N7"],
    "config": {"custom_pages": {"dir": "playgrounds", "output": "experiments"}},
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-raw-navbar-after",
            "version": "0.1.0",
            "description": "Test raw custom page navbar placement.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_custom_raw_navbar_after/__init__.py": (
            '"""Test package for raw custom page navbar placement."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_raw_navbar_after/core.py": '''
            """Core module for raw custom page tests."""


            def render(topic: str = "guide") -> str:
                """Return a simple label for API generation.

                Parameters
                ----------
                topic : str
                    A topic label.

                Returns
                -------
                str
                    The rendered topic.
                """
                return f"rendered: {topic}"
        ''',
        "user_guide/intro.qmd": "---\ntitle: Intro\n---\n\n# Intro\n\nUser guide intro.\n",
        "playgrounds/playground.html": """
            ---
            layout: raw
            navbar:
              text: Playground
              after: User Guide
            ---
            <!DOCTYPE html>
            <html>
              <head><title>Playground</title></head>
              <body>
                <main id="playground-root">Raw playground content</main>
              </body>
            </html>
        """,
        "README.md": (
            "# gdtest-custom-raw-navbar-after\n\n"
            "Synthetic package for raw custom page navbar-after coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-raw-navbar-after",
        "detected_module": "gdtest_custom_raw_navbar_after",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
        "user_guide_files": ["intro.qmd"],
    },
}
