"""
gdtest_ug_with_images — User guide referencing assets (image placeholders).

Dimensions: M1
Focus: User guide page that references an asset file (text placeholder for images).
"""

SPEC = {
    "name": "gdtest_ug_with_images",
    "description": "User guide with pages referencing assets like diagrams.",
    "dimensions": ["M1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-with-images",
            "version": "0.1.0",
            "description": "Test user guide with asset references.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_with_images/__init__.py": '"""Test package for user guide with image references."""\n',
        "gdtest_ug_with_images/core.py": '''
            """Core render/display functions."""


            def render(template: str) -> str:
                """Render a template string.

                Parameters
                ----------
                template : str
                    The template string to render.

                Returns
                -------
                str
                    The rendered output.

                Examples
                --------
                >>> render("Hello, {{ name }}")
                'Hello, World'
                """
                return template


            def display(content: str) -> None:
                """Display content to the user.

                Parameters
                ----------
                content : str
                    The content to display.

                Returns
                -------
                None

                Examples
                --------
                >>> display("Hello")
                """
                pass
        ''',
        "user_guide/visual-guide.qmd": (
            "---\n"
            "title: Visual Guide\n"
            "---\n"
            "\n"
            "# Visual Guide\n"
            "\n"
            "Below is a reference to an architecture diagram:\n"
            "\n"
            "See `../assets/diagram.txt` for the full diagram.\n"
            "\n"
            "The diagram shows the main components of the system.\n"
        ),
        "assets/diagram.txt": (
            "[Placeholder for architecture diagram]\n"
            "\n"
            "Component A --> Component B --> Component C\n"
        ),
        "README.md": ("# gdtest-v2-ug-with-images\n\nTest user guide with asset references.\n"),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/visual-guide.html",
        ],
        "files_contain": {
            "great-docs/user-guide/visual-guide.html": [
                "Visual Guide",
                "architecture diagram",
            ],
        },
    },
}
