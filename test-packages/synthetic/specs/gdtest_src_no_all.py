"""
gdtest_src_no_all — src/ layout + no __all__.

Dimensions: A2, B3, C4, D1, E6, F6, G1, H7
Focus: src/ layout where the module omits __all__, relying on griffe
       fallback for public-name discovery.
"""

SPEC = {
    "name": "gdtest_src_no_all",
    "description": "src/ layout without __all__ (griffe fallback)",
    "dimensions": ["A2", "B3", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-src-no-all",
            "version": "0.1.0",
            "description": "Test griffe fallback in src/ layout",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
        "tool": {
            "setuptools": {
                "package-dir": {"": "src"},
            },
        },
    },
    "files": {
        "src/gdtest_src_no_all/__init__.py": '''\
            """Package in src/ layout without __all__."""

            __version__ = "0.1.0"


            class Record:
                """
                A data record.

                Parameters
                ----------
                key
                    Record key.
                value
                    Record value.
                """

                def __init__(self, key: str, value: str):
                    self.key = key
                    self.value = value


            def fetch(key: str) -> str:
                """
                Fetch a value by key.

                Parameters
                ----------
                key
                    The key to look up.

                Returns
                -------
                str
                    The value.
                """
                return ""


            def store(key: str, value: str) -> None:
                """
                Store a key-value pair.

                Parameters
                ----------
                key
                    The key.
                value
                    The value.
                """
                pass


            def _internal_helper(x):
                """Private — should not appear."""
                return x
        ''',
        "README.md": """\
            # gdtest-src-no-all

            Tests griffe name discovery in src/ layout without __all__.
        """,
    },
    "expected": {
        "detected_name": "gdtest-src-no-all",
        "detected_module": "gdtest_src_no_all",
        "detected_parser": "numpy",
        "export_names": ["Record", "fetch", "store"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
