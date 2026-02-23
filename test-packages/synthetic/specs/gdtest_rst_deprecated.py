"""
gdtest_rst_deprecated — Tests .. deprecated:: directives in docstrings.

Dimensions: L2
Focus: RST deprecated directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_deprecated",
    "description": "Tests deprecated RST directives in docstrings",
    "dimensions": ["L2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-deprecated",
            "version": "0.1.0",
            "description": "Test deprecated RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_deprecated/__init__.py": '''\
            """Package testing deprecated RST directives."""

            __version__ = "0.1.0"
            __all__ = ["old_connect", "legacy_parse"]


            def old_connect(host: str) -> bool:
                """
                Connect to a host using the legacy protocol.

                Parameters
                ----------
                host
                    The hostname to connect to.

                Returns
                -------
                bool
                    True if connection was successful.

                .. deprecated:: 1.5
                    Use connect_v2() instead.
                """
                return True


            def legacy_parse(text: str) -> dict:
                """
                Parse text using the legacy parser.

                Parameters
                ----------
                text
                    The text to parse.

                Returns
                -------
                dict
                    The parsed result.

                .. deprecated:: 2.0
                    Use parse_modern() instead.
                """
                return {}
        ''',
        "README.md": """\
            # gdtest-v2-rst-deprecated

            Tests deprecated RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-deprecated",
        "detected_module": "gdtest_rst_deprecated",
        "detected_parser": "numpy",
        "export_names": ["legacy_parse", "old_connect"],
        "num_exports": 2,
    },
}
