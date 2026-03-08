"""
gdtest_announce_disabled — Tests announcement: false (explicitly disabled).

Dimensions: K27
Focus: announcement set to false produces no meta tag or script.
"""

SPEC = {
    "name": "gdtest_announce_disabled",
    "description": "Tests announcement banner explicitly disabled",
    "dimensions": ["K27"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-announce-disabled",
            "version": "0.1.0",
            "description": "Test announcement banner disabled",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "announcement": False,
    },
    "files": {
        "gdtest_announce_disabled/__init__.py": '''\
            """Package testing announcement banner disabled."""

            __version__ = "0.1.0"
            __all__ = ["process", "transform"]


            def process(data: list) -> list:
                """
                Process a list of data.

                Parameters
                ----------
                data
                    Input data list.

                Returns
                -------
                list
                    Processed data.
                """
                return [x for x in data if x]


            def transform(value: str) -> str:
                """
                Transform a string value.

                Parameters
                ----------
                value
                    The string to transform.

                Returns
                -------
                str
                    Transformed string.
                """
                return value.upper()
        ''',
    },
    "expected": {
        "export_names": ["process", "transform"],
        "section_titles": ["Functions"],
    },
}
