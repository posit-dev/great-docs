"""
gdtest_custom_basename_output — Nested source path using basename-derived output.

Dimensions: N7
Focus: String-form custom_pages config, nested source directories, `.htm`
input files, and default output basename handling.
"""

SPEC = {
    "name": "gdtest_custom_basename_output",
    "description": "Nested string custom_pages config with basename-derived output.",
    "dimensions": ["N7"],
    "config": {"custom_pages": "marketing/pages"},
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-basename-output",
            "version": "0.1.0",
            "description": "Test nested custom page source with basename-derived output.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_custom_basename_output/__init__.py": (
            '"""Test package for basename-derived custom page output."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_basename_output/core.py": '''
            """Core module for basename-derived custom page tests."""


            def render(topic: str = "basename") -> str:
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
        "marketing/pages/launch.htm": """
            ---
            title: Launch Home
            layout: passthrough
            navbar: Launch Home
            ---
            <section class="launch-home">
              <h1>Launch Home</h1>
              <p>Passthrough page sourced from a nested `.htm` file.</p>
            </section>
        """,
        "marketing/pages/assets/site.css": ":root { --launch-home: 1; }\n",
        "README.md": (
            "# gdtest-custom-basename-output\n\n"
            "Synthetic package for basename-derived custom page output coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-basename-output",
        "detected_module": "gdtest_custom_basename_output",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
    },
}
