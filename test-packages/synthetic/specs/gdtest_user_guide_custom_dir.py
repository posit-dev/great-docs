"""
gdtest_user_guide_custom_dir — Custom user guide directory path.

Dimensions: A1, B1, C1, D1, E6, F5, G1, H7
Focus: Uses config user_guide: "docs/guides" for non-standard directory.
       Tests non-standard directory resolution.
"""

SPEC = {
    "name": "gdtest_user_guide_custom_dir",
    "description": "Custom user guide directory path",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F5", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-custom-dir",
            "version": "0.1.0",
            "description": "A synthetic test package with custom user guide dir",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": "docs/guides",
    },
    "files": {
        "gdtest_user_guide_custom_dir/__init__.py": '''\
            """A test package with custom user guide directory."""

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
                    Fetched data.
                """
                return ""


            def store(data: str, path: str) -> None:
                """
                Store data to a path.

                Parameters
                ----------
                data
                    Data to store.
                path
                    Storage path.
                """
                pass
        ''',
        "docs/guides/intro.qmd": """\
            ---
            title: Introduction
            ---

            Welcome to the custom guide!
        """,
        "docs/guides/advanced.qmd": """\
            ---
            title: Advanced
            ---

            Advanced topics.
        """,
        "README.md": """\
            # gdtest-user-guide-custom-dir

            A synthetic test package with custom user guide directory.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-custom-dir",
        "detected_module": "gdtest_user_guide_custom_dir",
        "detected_parser": "numpy",
        "export_names": ["fetch", "store"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
