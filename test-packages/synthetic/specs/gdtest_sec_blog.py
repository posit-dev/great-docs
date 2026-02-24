"""
gdtest_sec_blog — Blog section using Quarto's native listing directive.

Dimensions: N4
Focus: Blog section with type "blog" that uses Quarto's listing feature.
Blog posts live in subdirectories with proper frontmatter (title, author, date).
"""

SPEC = {
    "name": "gdtest_sec_blog",
    "description": "Blog section using Quarto's native listing directive.",
    "dimensions": ["N4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-blog",
            "version": "0.1.0",
            "description": "Test blog section using Quarto listing.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Blog", "dir": "blog", "type": "blog"},
        ],
    },
    "files": {
        "gdtest_sec_blog/__init__.py": '"""Test package for blog section."""\n',
        "gdtest_sec_blog/core.py": '''
            """Core post/archive functions."""


            def post(title: str, content: str) -> dict:
                """Create a new blog post.

                Parameters
                ----------
                title : str
                    The title of the blog post.
                content : str
                    The content of the blog post.

                Returns
                -------
                dict
                    A dictionary representing the created post.

                Examples
                --------
                >>> post("Hello", "World")
                {'title': 'Hello', 'content': 'World'}
                """
                return {"title": title, "content": content}


            def archive(year: int) -> list:
                """Retrieve archived posts for a given year.

                Parameters
                ----------
                year : int
                    The year to retrieve posts from.

                Returns
                -------
                list
                    A list of archived posts for the given year.

                Examples
                --------
                >>> archive(2024)
                []
                """
                return []
        ''',
        "blog/introducing-our-project/index.qmd": (
            "---\n"
            "title: Introducing Our Project\n"
            "author: Jane Smith\n"
            "date: 2024-01-15\n"
            "categories: [announcements, getting-started]\n"
            "description: A blog post introducing the project and its goals.\n"
            "---\n"
            "\n"
            "A blog post introducing the project and its goals.\n"
            "\n"
            "We're excited to announce the launch of this project. "
            "Here's what you need to know.\n"
            "\n"
            "## Why We Built This\n"
            "\n"
            "We saw a need for better tooling in this space and decided to "
            "build something that addresses common pain points.\n"
            "\n"
            "## What's Next\n"
            "\n"
            "Stay tuned for updates as we continue to develop new features.\n"
        ),
        "blog/february-update/index.qmd": (
            "---\n"
            "title: February Update\n"
            "author: John Doe\n"
            "date: 2024-02-20\n"
            "categories: [updates]\n"
            "description: An update on the progress made in February 2024.\n"
            "---\n"
            "\n"
            "An update on the progress made in February 2024.\n"
            "\n"
            "## Highlights\n"
            "\n"
            "- Improved performance by 30%\n"
            "- Added support for new file formats\n"
            "- Fixed several reported bugs\n"
            "\n"
            "## Community Contributions\n"
            "\n"
            "Thanks to everyone who contributed this month!\n"
        ),
        "blog/v0.2-release/index.qmd": (
            "---\n"
            'title: "Version 0.2 Release Notes"\n'
            "author: Jane Smith\n"
            "date: 2024-03-10\n"
            "categories: [releases]\n"
            "description: Release notes for version 0.2 with new features.\n"
            "---\n"
            "\n"
            "We're happy to announce the v0.2 release!\n"
            "\n"
            "## New Features\n"
            "\n"
            "- Blog support via Quarto's listing directive\n"
            "- Improved dark mode styling\n"
            "- Better section card colors\n"
            "\n"
            "## Breaking Changes\n"
            "\n"
            "None in this release.\n"
        ),
        "README.md": ("# gdtest-v2-sec-blog\n\nTest blog section using Quarto listing.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-blog",
        "detected_module": "gdtest_sec_blog",
        "detected_parser": "numpy",
        "export_names": ["archive", "post"],
        "num_exports": 2,
    },
}
