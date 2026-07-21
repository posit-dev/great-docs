"""
gdtest_seealso_desc — %seealso directive with descriptions.

Dimensions: A1, D1, E3, L22
Focus: Tests the %seealso directive with ``name : description`` syntax.
       Descriptions should appear alongside links in the rendered See Also
       section.
"""

SPEC = {
    "name": "gdtest_seealso_desc",
    "description": (
        "%seealso directive with descriptions. "
        "Tests that 'name : description' entries render descriptions alongside links."
    ),
    "dimensions": ["A1", "D1", "E3", "L22"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-seealso-desc",
            "version": "0.1.0",
            "description": "Test %seealso with descriptions",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_seealso_desc/__init__.py": '''\
            """Package demonstrating %seealso with descriptions."""

            __version__ = "0.1.0"
            __all__ = ["load", "save", "validate", "transform"]


            def load(path: str) -> dict:
                """
                Load data from a file.

                %seealso save : Write data back to a file, validate : Check data integrity

                Parameters
                ----------
                path
                    The file path to read from.

                Returns
                -------
                dict
                    The loaded data.
                """
                return {}


            def save(data: dict, path: str) -> None:
                """
                Save data to a file.

                %seealso load : Read data from a file, transform : Transform data before saving

                Parameters
                ----------
                data
                    The data to save.
                path
                    The file path to write to.
                """
                pass


            def validate(data: dict) -> bool:
                """
                Validate data integrity.

                %seealso load, save

                Parameters
                ----------
                data
                    The data to validate.

                Returns
                -------
                bool
                    True if valid.
                """
                return True


            def transform(data: dict) -> dict:
                """
                Transform data before processing.

                %seealso validate : Check data integrity first

                Parameters
                ----------
                data
                    The data to transform.

                Returns
                -------
                dict
                    The transformed data.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-seealso-desc

            A synthetic test package testing ``%seealso`` with descriptions.
        """,
    },
    "expected": {
        "detected_name": "gdtest-seealso-desc",
        "detected_module": "gdtest_seealso_desc",
        "detected_parser": "numpy",
        "export_names": ["load", "save", "transform", "validate"],
        "num_exports": 4,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "seealso": {
            "load": ["save", "validate"],
            "save": ["load", "transform"],
            "validate": ["load", "save"],
            "transform": ["validate"],
        },
        "seealso_descriptions": {
            "load": {"save": "Write data back to a file", "validate": "Check data integrity"},
            "save": {"load": "Read data from a file", "transform": "Transform data before saving"},
            "transform": {"validate": "Check data integrity first"},
        },
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
