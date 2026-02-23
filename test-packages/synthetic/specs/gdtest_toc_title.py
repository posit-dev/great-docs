"""
gdtest_toc_title — Tests site.toc-title: 'Contents'.

Dimensions: Q6
Focus: Site config with toc-title set to 'Contents'.
"""

SPEC = {
    "name": "gdtest_toc_title",
    "description": "Tests site.toc-title: 'Contents' config.",
    "dimensions": ["Q6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-toc-title",
            "version": "0.1.0",
            "description": "Test site toc-title config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {"toc-title": "Contents"},
    },
    "files": {
        "gdtest_toc_title/__init__.py": '''\
            """Package testing site toc-title config."""

            __all__ = ["index", "lookup"]


            def index(items: list) -> dict:
                """Build an index from a list of items.

                Parameters
                ----------
                items : list
                    The items to index.

                Returns
                -------
                dict
                    A dictionary mapping each item to its position.

                Examples
                --------
                >>> index(["a", "b", "c"])
                {'a': 0, 'b': 1, 'c': 2}
                """
                return {item: i for i, item in enumerate(items)}


            def lookup(key: str) -> str:
                """Look up a value by key.

                Parameters
                ----------
                key : str
                    The key to look up.

                Returns
                -------
                str
                    The value associated with the key.

                Examples
                --------
                >>> lookup("name")
                'name'
                """
                return key
        ''',
        "README.md": ("# gdtest-v2-toc-title\n\nTest site toc-title config.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-toc-title",
        "detected_module": "gdtest_toc_title",
        "detected_parser": "numpy",
        "export_names": ["index", "lookup"],
        "num_exports": 2,
    },
}
