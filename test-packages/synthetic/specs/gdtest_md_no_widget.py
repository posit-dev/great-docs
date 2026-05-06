"""
gdtest_md_no_widget — Tests markdown_pages: {widget: false} config.

Dimensions: K24
Focus: markdown_pages config with widget disabled. The .md companion files
should still be generated but the copy-page widget should not appear in the HTML.
"""

SPEC = {
    "name": "gdtest_md_no_widget",
    "description": "Tests markdown_pages widget: false config",
    "dimensions": ["K24"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-md-no-widget",
            "version": "0.1.0",
            "description": "Test markdown_pages widget false config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "markdown_pages": {
            "widget": False,
        },
    },
    "files": {
        "gdtest_md_no_widget/__init__.py": '''\
            """Package testing markdown_pages widget false config."""

            __version__ = "0.1.0"
            __all__ = ["encode", "decode"]


            def encode(data: str) -> bytes:
                """
                Encode a string to bytes.

                Parameters
                ----------
                data
                    The string to encode.

                Returns
                -------
                bytes
                    The encoded bytes.
                """
                return data.encode("utf-8")


            def decode(data: bytes) -> str:
                """
                Decode bytes to a string.

                Parameters
                ----------
                data
                    The bytes to decode.

                Returns
                -------
                str
                    The decoded string.
                """
                return data.decode("utf-8")
        ''',
        "README.md": """\
            # gdtest-md-no-widget

            Tests markdown_pages with widget: false. The .md companion files
            should be generated but the copy-page widget should not appear.
        """,
    },
    "expected": {
        "detected_name": "gdtest-md-no-widget",
        "detected_module": "gdtest_md_no_widget",
        "detected_parser": "numpy",
        "export_names": ["decode", "encode"],
        "num_exports": 2,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'sechdg', 'sbsec', 'hdg'],
},
}
