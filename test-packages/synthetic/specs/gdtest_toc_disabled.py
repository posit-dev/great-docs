"""
gdtest_toc_disabled — Tests site.toc: false.

Dimensions: Q4
Focus: Site config with table of contents disabled.
"""

SPEC = {
    "name": "gdtest_toc_disabled",
    "description": "Tests site.toc: false config.",
    "dimensions": ["Q4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-toc-disabled",
            "version": "0.1.0",
            "description": "Test site toc disabled config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {"toc": False},
    },
    "files": {
        "gdtest_toc_disabled/__init__.py": '''\
            """Package testing site toc disabled config."""

            __all__ = ["navigate", "bookmark"]


            def navigate(path: str) -> str:
                """Navigate to the given path.

                Parameters
                ----------
                path : str
                    The path to navigate to.

                Returns
                -------
                str
                    The resolved navigation path.

                Examples
                --------
                >>> navigate("/home")
                '/home'
                """
                return path


            def bookmark(page: str) -> int:
                """Bookmark a page and return the bookmark ID.

                Parameters
                ----------
                page : str
                    The page to bookmark.

                Returns
                -------
                int
                    The bookmark ID.

                Examples
                --------
                >>> bookmark("index")
                1
                """
                return 1
        ''',
        "README.md": ("# gdtest-v2-toc-disabled\n\nTest site toc disabled config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-toc-disabled",
        "detected_module": "gdtest_toc_disabled",
        "detected_parser": "numpy",
        "export_names": ["bookmark", "navigate"],
        "num_exports": 2,
    },
}
