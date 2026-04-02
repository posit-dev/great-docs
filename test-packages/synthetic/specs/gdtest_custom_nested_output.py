"""
gdtest_custom_nested_output — Custom pages published under a nested output prefix.

Dimensions: N7
Focus: Output prefixes containing path separators and copied resources under
that nested deployed path.
"""

SPEC = {
    "name": "gdtest_custom_nested_output",
    "description": "Custom page output published under a nested URL prefix.",
    "dimensions": ["N7"],
    "config": {"custom_pages": {"dir": "apps", "output": "products/python"}},
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-nested-output",
            "version": "0.1.0",
            "description": "Test nested output prefixes for custom pages.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_custom_nested_output/__init__.py": (
            '"""Test package for nested custom page output prefixes."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_nested_output/core.py": '''
            """Core module for nested output prefix tests."""


            def render(topic: str = "nested-output") -> str:
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
        "apps/start.html": """
            ---
            title: Python Apps
            layout: passthrough
            navbar: true
            ---
            <section class="python-apps">
              <h1>Python Apps</h1>
              <p>Custom page published under a nested output prefix.</p>
            </section>
        """,
        "apps/assets/widget.js": "window.GDTEST_NESTED_OUTPUT = true;\n",
        "README.md": (
            "# gdtest-custom-nested-output\n\n"
            "Synthetic package for nested custom page output prefix coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-nested-output",
        "detected_module": "gdtest_custom_nested_output",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
    },
}
