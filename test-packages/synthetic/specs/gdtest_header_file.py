"""
gdtest_header_file — Tests include_in_header with a file reference.

Dimensions: K42
Focus: include_in_header with a {file: ...} entry reads from an external file.
"""

SPEC = {
    "name": "gdtest_header_file",
    "description": "Tests include_in_header with a file reference",
    "dimensions": ["K42"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-header-file",
            "version": "0.1.0",
            "description": "Test include_in_header file config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "include_in_header": [
            {"file": "../custom-head.html"},
        ],
    },
    "files": {
        "gdtest_header_file/__init__.py": '''\
            """Package testing include_in_header with a file reference."""

            __version__ = "0.1.0"
            __all__ = ["divide", "negate"]


            def divide(a: float, b: float) -> float:
                """
                Divide a by b.

                Parameters
                ----------
                a
                    Numerator.
                b
                    Denominator.

                Returns
                -------
                float
                    Quotient.
                """
                return a / b


            def negate(x: float) -> float:
                """
                Negate a number.

                Parameters
                ----------
                x
                    The number to negate.

                Returns
                -------
                float
                    Negated value.
                """
                return -x
        ''',
        "custom-head.html": """\
            <meta name="gd-file-inject" content="from-external-file">
        """,
    },
    "expected": {
        "export_names": ["divide", "negate"],
        "section_titles": ["Functions"],
    },
}
