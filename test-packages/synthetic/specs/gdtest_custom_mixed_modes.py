"""
gdtest_custom_mixed_modes — Mixed passthrough/raw custom pages with assets.

Dimensions: N7
Focus: Multiple custom pages with mixed layouts, copied assets, and selective
navbar exposure.
"""

SPEC = {
    "name": "gdtest_custom_mixed_modes",
    "description": "Mixed passthrough/raw custom pages with copied assets.",
    "dimensions": ["N7"],
    "config": {
        "custom_pages": [
            {"dir": "marketing", "output": "py"},
            {"dir": "playgrounds", "output": "demos"},
        ]
    },
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-mixed-modes",
            "version": "0.1.0",
            "description": "Test mixed custom page layouts and assets.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_custom_mixed_modes/__init__.py": (
            '"""Test package for mixed custom page modes."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_mixed_modes/core.py": '''
            """Core module for mixed custom mode tests."""


            def render(topic: str = "launchpad") -> str:
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
        "marketing/launchpad.html": """
            ---
            title: Launchpad
            layout: passthrough
            navbar: true
            ---
            <section class="launchpad-hero">
              <h1>Launchpad</h1>
              <p>Custom passthrough content with the Great Docs shell.</p>
            </section>
        """,
        "playgrounds/widget.html": """
            ---
            layout: raw
            navbar: Widget Lab
            ---
            <!DOCTYPE html>
            <html>
              <head><title>Widget Lab</title></head>
              <body>
                <script src="assets/chart.js"></script>
                <div id="widget-lab">Raw widget lab</div>
              </body>
            </html>
        """,
        "marketing/hidden.html": """
            ---
            title: Hidden Canvas
            layout: passthrough
            ---
            <section><p>This page should not appear in the navbar.</p></section>
        """,
        "playgrounds/assets/chart.js": "window.GDTEST_CUSTOM_CHART = true;\n",
        "README.md": (
            "# gdtest-custom-mixed-modes\n\nSynthetic package for mixed custom page coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-mixed-modes",
        "detected_module": "gdtest_custom_mixed_modes",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
    },
}
