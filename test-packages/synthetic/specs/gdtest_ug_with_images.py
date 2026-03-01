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
            "name": "gdtest-ug-with-images",
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
            "Below is the architecture diagram showing how the main components connect:\n"
            "\n"
            "![Architecture Diagram](../assets/architecture.svg)\n"
            "\n"
            "The diagram above shows the main components of the system.\n"
            "\n"
            "## Data Flow\n"
            "\n"
            "The following diagram illustrates the data flow between components:\n"
            "\n"
            "![Data Flow Diagram](../assets/data-flow.svg)\n"
            "\n"
            "Data moves from ingestion through processing to storage.\n"
        ),
        "assets/architecture.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 120">\n'
            '  <rect x="10" y="40" width="100" height="40" rx="6" fill="#4A90D9" stroke="#2C5F8A" stroke-width="2"/>\n'
            '  <text x="60" y="65" text-anchor="middle" fill="white" font-size="14">Component A</text>\n'
            '  <line x1="110" y1="60" x2="150" y2="60" stroke="#333" stroke-width="2" marker-end="url(#arrow)"/>\n'
            '  <rect x="150" y="40" width="100" height="40" rx="6" fill="#7B68EE" stroke="#5A4CBE" stroke-width="2"/>\n'
            '  <text x="200" y="65" text-anchor="middle" fill="white" font-size="14">Component B</text>\n'
            '  <line x1="250" y1="60" x2="290" y2="60" stroke="#333" stroke-width="2" marker-end="url(#arrow)"/>\n'
            '  <rect x="290" y="40" width="100" height="40" rx="6" fill="#3CB371" stroke="#2D8659" stroke-width="2"/>\n'
            '  <text x="340" y="65" text-anchor="middle" fill="white" font-size="14">Component C</text>\n'
            '  <defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">\n'
            '    <path d="M 0 0 L 10 5 L 0 10 z" fill="#333"/>\n'
            "  </marker></defs>\n"
            "</svg>\n"
        ),
        "assets/data-flow.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 160">\n'
            '  <rect x="150" y="5" width="100" height="30" rx="4" fill="#F0AD4E" stroke="#C68E2C" stroke-width="2"/>\n'
            '  <text x="200" y="25" text-anchor="middle" fill="white" font-size="12">Ingestion</text>\n'
            '  <line x1="200" y1="35" x2="200" y2="55" stroke="#333" stroke-width="2" marker-end="url(#arr)"/>\n'
            '  <rect x="150" y="55" width="100" height="30" rx="4" fill="#5BC0DE" stroke="#3AA8C7" stroke-width="2"/>\n'
            '  <text x="200" y="75" text-anchor="middle" fill="white" font-size="12">Processing</text>\n'
            '  <line x1="200" y1="85" x2="200" y2="105" stroke="#333" stroke-width="2" marker-end="url(#arr)"/>\n'
            '  <rect x="150" y="105" width="100" height="30" rx="4" fill="#D9534F" stroke="#B94441" stroke-width="2"/>\n'
            '  <text x="200" y="125" text-anchor="middle" fill="white" font-size="12">Storage</text>\n'
            '  <defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">\n'
            '    <path d="M 0 0 L 10 5 L 0 10 z" fill="#333"/>\n'
            "  </marker></defs>\n"
            "</svg>\n"
        ),
        "README.md": ("# gdtest-ug-with-images\n\nTest user guide with asset references.\n"),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/visual-guide.html",
        ],
        "files_contain": {
            "great-docs/user-guide/visual-guide.html": [
                "Visual Guide",
                "architecture diagram",
                "<img",
                "Architecture Diagram",
                "Data Flow",
            ],
        },
    },
}
