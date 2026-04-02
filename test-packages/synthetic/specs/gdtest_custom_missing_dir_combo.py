"""
gdtest_custom_missing_dir_combo — One configured custom page directory is absent.

Dimensions: N7
Focus: Multi-entry custom_pages config should skip missing directories while
still rendering valid entries and resource metadata correctly.
"""

SPEC = {
    "name": "gdtest_custom_missing_dir_combo",
    "description": "Missing custom page dir is skipped while valid entries still render.",
    "dimensions": ["N7"],
    "config": {
        "custom_pages": [
            {"dir": "ghost-pages", "output": "ghost"},
            {"dir": "playgrounds", "output": "demos"},
        ]
    },
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-missing-dir-combo",
            "version": "0.1.0",
            "description": "Test missing custom page directories alongside valid ones.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_custom_missing_dir_combo/__init__.py": (
            '"""Test package for missing custom page directory handling."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_missing_dir_combo/core.py": '''
            """Core module for missing custom page directory tests."""


            def render(topic: str = "missing-dir") -> str:
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
        "playgrounds/widget.html": """
            ---
            layout: raw
            navbar: Widget Lab
            ---
            <!DOCTYPE html>
            <html>
              <head><title>Widget Lab</title></head>
              <body>
                <main id="widget-lab">Only the existing custom dir should render.</main>
              </body>
            </html>
        """,
        "README.md": (
            "# gdtest-custom-missing-dir-combo\n\n"
            "Synthetic package for missing custom page directory coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-missing-dir-combo",
        "detected_module": "gdtest_custom_missing_dir_combo",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
    },
}
