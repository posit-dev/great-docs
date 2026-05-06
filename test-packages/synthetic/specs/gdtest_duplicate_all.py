"""
gdtest_duplicate_all — __all__ with duplicate entries.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Module where __all__ accidentally lists the same name twice.
       Tests graceful deduplication without crash.
"""

SPEC = {
    "name": "gdtest_duplicate_all",
    "description": "__all__ with duplicate entries",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-duplicate-all",
            "version": "0.1.0",
            "description": "Test duplicate __all__ handling",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_duplicate_all/__init__.py": '''\
            """Module with duplicate __all__ entries."""

            __version__ = "0.1.0"
            __all__ = ["transform", "validate", "transform"]  # duplicate!


            def transform(data: str) -> str:
                """
                Transform input data.

                Parameters
                ----------
                data
                    Input data.

                Returns
                -------
                str
                    Transformed data.
                """
                return data.upper()


            def validate(data: str) -> bool:
                """
                Validate input data.

                Parameters
                ----------
                data
                    Input data.

                Returns
                -------
                bool
                    True if valid.
                """
                return len(data) > 0
        ''',
        "README.md": """\
            # gdtest-duplicate-all

            Tests graceful handling of duplicate __all__ entries.
        """,
    },
    "expected": {
        "detected_name": "gdtest-duplicate-all",
        "detected_module": "gdtest_duplicate_all",
        "detected_parser": "numpy",
        "export_names": ["transform", "validate"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
