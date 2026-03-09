"""
gdtest_header_text — Tests include_in_header with a single inline string.

Dimensions: K40
Focus: include_in_header as a plain string adds a custom meta tag to <head>.
"""

SPEC = {
    "name": "gdtest_header_text",
    "description": "Tests include_in_header with a single inline string",
    "dimensions": ["K40"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-header-text",
            "version": "0.1.0",
            "description": "Test include_in_header string config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "include_in_header": '<meta name="gd-custom-test" content="header-text-injected">',
    },
    "files": {
        "gdtest_header_text/__init__.py": '''\
            """Package testing include_in_header with a string."""

            __version__ = "0.1.0"
            __all__ = ["add", "multiply"]


            def add(a: int, b: int) -> int:
                """
                Add two numbers.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    Sum.
                """
                return a + b


            def multiply(a: int, b: int) -> int:
                """
                Multiply two numbers.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    Product.
                """
                return a * b
        ''',
    },
    "expected": {
        "export_names": ["add", "multiply"],
        "section_titles": ["Functions"],
    },
}
