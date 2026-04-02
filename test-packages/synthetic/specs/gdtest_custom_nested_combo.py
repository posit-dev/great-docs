"""
gdtest_custom_nested_combo — Nested custom page with sections and user guide.

Dimensions: N7
Focus: Nested passthrough custom page path plus navbar ordering with user guide
and configured sections.
"""

SPEC = {
    "name": "gdtest_custom_nested_combo",
    "description": "Nested custom page with user guide and section navbar ordering.",
    "dimensions": ["N7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-custom-nested-combo",
            "version": "0.1.0",
            "description": "Test nested custom pages with section coexistence.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [{"title": "Tutorials", "dir": "tutorials", "navbar_after": "User Guide"}],
        "custom_pages": {"dir": "apps", "output": "py"},
    },
    "files": {
        "gdtest_custom_nested_combo/__init__.py": (
            '"""Test package for nested custom page combinations."""\n\n'
            "from .core import render\n\n"
            '__all__ = ["render"]\n'
        ),
        "gdtest_custom_nested_combo/core.py": '''
            """Core module for nested custom combination tests."""


            def render(topic: str = "lab") -> str:
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
        "user_guide/start.qmd": "---\ntitle: Start\n---\n\n# Start\n\nGuide start.\n",
        "tutorials/first.qmd": "---\ntitle: First Tutorial\n---\n\n# First Tutorial\n\nTutorial page.\n",
        "apps/tools/lab.html": """
            ---
            title: API Lab
            layout: passthrough
            navbar:
              text: API Lab
              after: Tutorials
            ---
            <section class="api-lab">
              <h1>API Lab</h1>
              <p>Nested custom passthrough page.</p>
            </section>
        """,
        "README.md": (
            "# gdtest-custom-nested-combo\n\n"
            "Synthetic package for nested custom page combination coverage.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-custom-nested-combo",
        "detected_module": "gdtest_custom_nested_combo",
        "detected_parser": "numpy",
        "export_names": ["render"],
        "num_exports": 1,
        "user_guide_files": ["start.qmd"],
    },
}
