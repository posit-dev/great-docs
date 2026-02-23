"""
gdtest_sec_blog — Custom "Blog" section with date-prefixed pages.

Dimensions: N4
Focus: Custom section with title "Blog" sourced from blog/ directory with date-prefixed filenames.
"""

SPEC = {
    "name": "gdtest_sec_blog",
    "description": "Custom 'Blog' section with date-prefixed pages via sections config.",
    "dimensions": ["N4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-blog",
            "version": "0.1.0",
            "description": "Test custom Blog section with date-prefixed pages.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Blog", "dir": "blog"},
        ],
    },
    "files": {
        "gdtest_sec_blog/__init__.py": '"""Test package for custom Blog section."""\n',
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
        "blog/2024-01-intro.qmd": (
            "---\n"
            "title: Introducing Our Project\n"
            "---\n"
            "\n"
            "# Introducing Our Project\n"
            "\n"
            "A blog post introducing the project and its goals.\n"
        ),
        "blog/2024-02-update.qmd": (
            "---\n"
            "title: February Update\n"
            "---\n"
            "\n"
            "# February Update\n"
            "\n"
            "An update on the progress made in February 2024.\n"
        ),
        "README.md": (
            "# gdtest-v2-sec-blog\n\nTest custom Blog section with date-prefixed pages.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-blog",
        "detected_module": "gdtest_sec_blog",
        "detected_parser": "numpy",
        "export_names": ["archive", "post"],
        "num_exports": 2,
    },
}
