"""
gdtest_md_disabled — Tests markdown_pages: false config.

Dimensions: K23
Focus: markdown_pages config option set to false to disable .md generation
and the copy-page widget entirely.
"""

SPEC = {
    "name": "gdtest_md_disabled",
    "description": "Tests markdown_pages: false config",
    "dimensions": ["K23"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-md-disabled",
            "version": "0.1.0",
            "description": "Test markdown_pages false config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "markdown_pages": False,
    },
    "files": {
        "gdtest_md_disabled/__init__.py": '''\
            """Package testing markdown_pages false config."""

            __version__ = "0.1.0"
            __all__ = ["compute", "validate"]


            def compute(x: int, y: int) -> int:
                """
                Compute the sum of two integers.

                Parameters
                ----------
                x
                    First operand.
                y
                    Second operand.

                Returns
                -------
                int
                    The sum of x and y.
                """
                return x + y


            def validate(value: str) -> bool:
                """
                Validate a string value.

                Parameters
                ----------
                value
                    The string to validate.

                Returns
                -------
                bool
                    True if the value is non-empty.
                """
                return bool(value)
        ''',
        "README.md": """\
            # gdtest-md-disabled

            Tests markdown_pages: false config. No .md files should be generated
            and the copy-page widget should not appear.
        """,
    },
    "expected": {
        "detected_name": "gdtest-md-disabled",
        "detected_module": "gdtest_md_disabled",
        "detected_parser": "numpy",
        "export_names": ["compute", "validate"],
        "num_exports": 2,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'sechdg', 'sbsec', 'hdg'],
},
}
