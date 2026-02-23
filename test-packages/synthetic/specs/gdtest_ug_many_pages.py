"""
gdtest_ug_many_pages — User guide with twelve pages.

Dimensions: M8
Focus: User guide with a large number of numbered pages.
"""

SPEC = {
    "name": "gdtest_ug_many_pages",
    "description": "User guide with 12 numbered pages from overview to appendix.",
    "dimensions": ["M8"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-many-pages",
            "version": "0.1.0",
            "description": "Test user guide with many pages.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_many_pages/__init__.py": '"""Test package for many-page user guide."""\n',
        "gdtest_ug_many_pages/core.py": '''
            """Core browse/search functions."""


            def browse(page: int) -> str:
                """Browse to a specific page by number.

                Parameters
                ----------
                page : int
                    The page number to browse to.

                Returns
                -------
                str
                    The content of the requested page.

                Examples
                --------
                >>> browse(1)
                'Page 1 content'
                """
                return f"Page {page} content"


            def search(query: str) -> list:
                """Search all pages for the given query string.

                Parameters
                ----------
                query : str
                    The search query to match.

                Returns
                -------
                list
                    A list of page numbers that match the query.

                Examples
                --------
                >>> search("install")
                [2, 5]
                """
                return []
        ''',
        "user_guide/01-overview.qmd": (
            "---\n"
            "title: Overview\n"
            "---\n"
            "\n"
            "# Overview\n"
            "\n"
            "A high-level overview of the entire project.\n"
        ),
        "user_guide/02-installation.qmd": (
            "---\n"
            "title: Installation\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "Step-by-step installation instructions.\n"
        ),
        "user_guide/03-quickstart.qmd": (
            "---\ntitle: Quickstart\n---\n\n# Quickstart\n\nGet up and running in minutes.\n"
        ),
        "user_guide/04-configuration.qmd": (
            "---\n"
            "title: Configuration\n"
            "---\n"
            "\n"
            "# Configuration\n"
            "\n"
            "All available configuration options.\n"
        ),
        "user_guide/05-basic-usage.qmd": (
            "---\ntitle: Basic Usage\n---\n\n# Basic Usage\n\nCommon patterns for everyday use.\n"
        ),
        "user_guide/06-advanced-usage.qmd": (
            "---\n"
            "title: Advanced Usage\n"
            "---\n"
            "\n"
            "# Advanced Usage\n"
            "\n"
            "Power-user techniques and advanced patterns.\n"
        ),
        "user_guide/07-plugins.qmd": (
            "---\ntitle: Plugins\n---\n\n# Plugins\n\nHow to use and create plugins.\n"
        ),
        "user_guide/08-testing.qmd": (
            "---\ntitle: Testing\n---\n\n# Testing\n\nBest practices for testing your project.\n"
        ),
        "user_guide/09-deployment.qmd": (
            "---\n"
            "title: Deployment\n"
            "---\n"
            "\n"
            "# Deployment\n"
            "\n"
            "Deploying your application to production.\n"
        ),
        "user_guide/10-troubleshooting.qmd": (
            "---\n"
            "title: Troubleshooting\n"
            "---\n"
            "\n"
            "# Troubleshooting\n"
            "\n"
            "Solutions to common problems and issues.\n"
        ),
        "user_guide/11-faq.qmd": (
            "---\ntitle: FAQ\n---\n\n# FAQ\n\nFrequently asked questions and answers.\n"
        ),
        "user_guide/12-appendix.qmd": (
            "---\n"
            "title: Appendix\n"
            "---\n"
            "\n"
            "# Appendix\n"
            "\n"
            "Supplementary materials and reference tables.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/01-overview.html",
            "great-docs/user-guide/02-installation.html",
            "great-docs/user-guide/03-quickstart.html",
            "great-docs/user-guide/04-configuration.html",
            "great-docs/user-guide/05-basic-usage.html",
            "great-docs/user-guide/06-advanced-usage.html",
            "great-docs/user-guide/07-plugins.html",
            "great-docs/user-guide/08-testing.html",
            "great-docs/user-guide/09-deployment.html",
            "great-docs/user-guide/10-troubleshooting.html",
            "great-docs/user-guide/11-faq.html",
            "great-docs/user-guide/12-appendix.html",
        ],
        "files_contain": {
            "great-docs/user-guide/01-overview.html": ["Overview"],
            "great-docs/user-guide/06-advanced-usage.html": ["Advanced Usage"],
            "great-docs/user-guide/12-appendix.html": ["Appendix"],
        },
    },
}
