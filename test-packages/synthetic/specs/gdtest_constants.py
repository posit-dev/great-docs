"""
gdtest_constants — Module-level constants and type aliases.

Dimensions: A1, B1, C12, D1, E6, F6, G1, H7
Focus: Constants (VERSION, DEFAULT_TIMEOUT), type aliases
       (HandlerFunc = Callable[..., None]). Tests non-callable export handling.
"""

SPEC = {
    "name": "gdtest_constants",
    "description": "Constants and type aliases",
    "dimensions": ["A1", "B1", "C12", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-constants",
            "version": "0.1.0",
            "description": "A synthetic test package with constants and type aliases",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_constants/__init__.py": '''\
            """A test package with constants and type aliases."""

            __version__ = "0.1.0"
            __all__ = [
                "DEFAULT_TIMEOUT",
                "MAX_RETRIES",
                "SUPPORTED_FORMATS",
                "HandlerFunc",
                "process",
            ]

            from typing import Callable

            DEFAULT_TIMEOUT: int = 30
            """Default timeout in seconds for network operations."""

            MAX_RETRIES: int = 3
            """Maximum number of retry attempts."""

            SUPPORTED_FORMATS: list[str] = ["json", "csv", "xml"]
            """List of supported output formats."""

            HandlerFunc = Callable[..., None]
            """Type alias for event handler functions."""


            def process(data: str, timeout: int = DEFAULT_TIMEOUT) -> str:
                """
                Process data with a timeout.

                Parameters
                ----------
                data
                    The input data.
                timeout
                    Timeout in seconds.

                Returns
                -------
                str
                    Processed data.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-constants

            A synthetic test package with constants and type aliases.
        """,
    },
    "expected": {
        "detected_name": "gdtest-constants",
        "detected_module": "gdtest_constants",
        "detected_parser": "numpy",
        "export_names": [
            "DEFAULT_TIMEOUT",
            "MAX_RETRIES",
            "SUPPORTED_FORMATS",
            "HandlerFunc",
            "process",
        ],
        "nodoc_items": ["HandlerFunc"],
        "num_exports": 5,
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec", "hdg"],
    },
}
