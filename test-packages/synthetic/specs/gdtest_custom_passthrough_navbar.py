"""
gdtest_custom_passthrough_navbar — Passthrough custom page linked in navbar.

Dimensions: N7
Focus: End-to-end rendering of a custom HTML passthrough page that opts into
the site navbar.
"""

SPEC = {
    "name": "gdtest_custom_passthrough_navbar",
    "description": "Passthrough custom HTML page with navbar integration.",
    "dimensions": ["N7"],
    "config": {"custom_pages": {"dir": "marketing", "output": "py"}},
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-passthrough-navbar",
            "version": "0.1.0",
            "description": "Test passthrough custom page navbar rendering.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_custom_passthrough_navbar/__init__.py": (
            '"""Test package for passthrough custom page navbar rendering."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_passthrough_navbar/core.py": '''
            """Core module for passthrough navbar tests."""


            def render(topic: str = "widgets") -> str:
                """Return a simple string for API generation.

                Parameters
                ----------
                topic : str
                    The topic to render.

                Returns
                -------
                str
                    A rendered label.
                """
                return f"rendered: {topic}"
        ''',
        "marketing/index.html": """
            ---
            title: Shiny for Python
            layout: passthrough
            navbar: true
            ---
            <section class="hero-banner">
              <h1>Reactive Python apps</h1>
              <p>Build interactive apps with a custom landing page.</p>
            </section>
        """,
        "README.md": (
            "# gdtest-custom-passthrough-navbar\n\n"
            "Synthetic package for passthrough custom page navbar coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-passthrough-navbar",
        "detected_module": "gdtest_custom_passthrough_navbar",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
    },
}
