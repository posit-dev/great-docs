"""
gdtest_sec_blog_user_index — Blog section with a user-provided index.qmd.

Dimensions: N4
Focus: Blog section where the user provides their own blog/index.qmd
(e.g., with a custom listing type) instead of relying on auto-generation.
The blog index should still get toc: false and body-classes: gd-blog-index
injected by Great Docs.
"""

SPEC = {
    "name": "gdtest_sec_blog_user_index",
    "description": "Blog section with user-provided index.qmd.",
    "dimensions": ["N4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-blog-user-index",
            "version": "0.1.0",
            "description": "Test blog section with user-provided listing index.",
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
        "gdtest_sec_blog_user_index/__init__.py": (
            '"""Test package for blog section with user index."""\n'
            "\n"
            "from .core import publish, draft\n"
            "\n"
            '__all__ = ["publish", "draft"]\n'
        ),
        "gdtest_sec_blog_user_index/core.py": '''
            """Core blog helpers."""


            def publish(title: str, body: str) -> dict:
                """Publish a blog post.

                Parameters
                ----------
                title : str
                    The post title.
                body : str
                    The post body.

                Returns
                -------
                dict
                    The published post record.

                Examples
                --------
                >>> publish("Hello", "World")
                {'title': 'Hello', 'body': 'World', 'status': 'published'}
                """
                return {"title": title, "body": body, "status": "published"}


            def draft(title: str) -> dict:
                """Create a draft post.

                Parameters
                ----------
                title : str
                    The draft title.

                Returns
                -------
                dict
                    The draft post record.

                Examples
                --------
                >>> draft("WIP")
                {'title': 'WIP', 'status': 'draft'}
                """
                return {"title": title, "status": "draft"}
        ''',
        # User-provided blog index with a custom listing type (table)
        # and a co-located header image referenced via relative path
        "blog/index.qmd": (
            "---\n"
            "title: Blog\n"
            "listing:\n"
            "  type: table\n"
            '  sort: "date desc"\n'
            "  feed: true\n"
            "  contents:\n"
            '    - "**.qmd"\n'
            "---\n"
            "\n"
            "![](./blog-header.svg)\n"
            "\n"
            "Welcome to our blog.\n"
        ),
        # Co-located SVG image referenced by the blog index
        "blog/blog-header.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="80">'
            '<rect width="400" height="80" fill="#4a90d9" rx="8"/>'
            '<text x="200" y="48" text-anchor="middle" fill="white" '
            'font-size="24" font-family="sans-serif">Blog</text></svg>\n'
        ),
        "blog/first-post/index.qmd": (
            "---\n"
            "title: First Post\n"
            "author: Alice\n"
            "date: 2024-03-01\n"
            "categories: [announcements]\n"
            "description: Our very first blog post.\n"
            "image: post-banner.svg\n"
            "---\n"
            "\n"
            "This is the first post on our blog.\n"
            "\n"
            "![](post-banner.svg)\n"
            "\n"
            "## Getting Started\n"
            "\n"
            "We're excited to share our work with you.\n"
        ),
        # Co-located image inside a blog post subdirectory
        "blog/first-post/post-banner.svg": (
            '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="60">'
            '<rect width="300" height="60" fill="#5cb85c" rx="6"/>'
            '<text x="150" y="38" text-anchor="middle" fill="white" '
            'font-size="18" font-family="sans-serif">First Post</text></svg>\n'
        ),
        "blog/second-post/index.qmd": (
            "---\n"
            "title: Second Post\n"
            "author: Bob\n"
            "date: 2024-04-15\n"
            "categories: [updates]\n"
            "description: A follow-up with new features.\n"
            "---\n"
            "\n"
            "Here's what we've been working on.\n"
            "\n"
            "## New Features\n"
            "\n"
            "- Improved performance\n"
            "- Better error messages\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest_sec_blog_user_index",
        "has_reference": True,
        "all_names": ["publish", "draft"],
        "ref_pages": ["publish.html", "draft.html"],
        "has_user_guide": False,
        "user_guide_pages": [],
    },
}
