"""
gdtest_github_icon — Tests github_style: 'icon' config.

Dimensions: K1
Focus: github_style config option set to 'icon' instead of default 'widget'.
"""

SPEC = {
    "name": "gdtest_github_icon",
    "description": "Tests github_style: icon config",
    "dimensions": ["K1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-github-icon",
            "version": "0.1.0",
            "description": "Test github_style icon config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "github_style": "icon",
    },
    "files": {
        "gdtest_github_icon/__init__.py": '''\
            """Package testing github_style icon config."""

            __version__ = "0.1.0"
            __all__ = ["fetch", "store"]


            def fetch(url: str) -> str:
                """
                Fetch data from a URL.

                Parameters
                ----------
                url
                    The URL to fetch from.

                Returns
                -------
                str
                    The fetched content.
                """
                return ""


            def store(key: str, value: str) -> None:
                """
                Store a key-value pair.

                Parameters
                ----------
                key
                    Storage key.
                value
                    Value to store.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-v2-github-icon

            Tests github_style: icon config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-github-icon",
        "detected_module": "gdtest_github_icon",
        "detected_parser": "numpy",
        "export_names": ["fetch", "store"],
        "num_exports": 2,
    },
}
