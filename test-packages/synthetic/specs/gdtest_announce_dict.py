"""
gdtest_announce_dict — Tests announcement banner with dict config.

Dimensions: K26
Focus: announcement config dict with type, url, and dismissable options.
"""

SPEC = {
    "name": "gdtest_announce_dict",
    "description": "Tests announcement banner with dict config (type, url, dismissable)",
    "dimensions": ["K26"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-announce-dict",
            "version": "0.1.0",
            "description": "Test announcement banner dict config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "announcement": {
            "content": "Version 2.0 is here!",
            "type": "success",
            "dismissable": False,
            "url": "https://example.com/changelog",
        },
    },
    "files": {
        "gdtest_announce_dict/__init__.py": '''\
            """Package testing announcement banner with dict config."""

            __version__ = "0.1.0"
            __all__ = ["compute", "validate"]


            def compute(x: int, y: int) -> int:
                """
                Compute the sum of two values.

                Parameters
                ----------
                x
                    First value.
                y
                    Second value.

                Returns
                -------
                int
                    The sum of x and y.
                """
                return x + y


            def validate(data: dict) -> bool:
                """
                Validate a data dictionary.

                Parameters
                ----------
                data
                    The data to validate.

                Returns
                -------
                bool
                    True if the data is valid.
                """
                return bool(data)
        ''',
    },
    "expected": {
        "export_names": ["compute", "validate"],
        "section_titles": ["Functions"],
    },
}
