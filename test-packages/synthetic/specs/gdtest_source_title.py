"""
gdtest_source_title — Tests source.placement: 'title' config.

Dimensions: K4
Focus: source.placement config option set to 'title'.
"""

SPEC = {
    "name": "gdtest_source_title",
    "description": "Tests source.placement: title config",
    "dimensions": ["K4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-source-title",
            "version": "0.1.0",
            "description": "Test source.placement title config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "source": {
            "placement": "title",
        },
    },
    "files": {
        "gdtest_source_title/__init__.py": '''\
            """Package testing source.placement title config."""

            __version__ = "0.1.0"
            __all__ = ["compress", "decompress"]


            def compress(data: bytes) -> bytes:
                """
                Compress binary data.

                Parameters
                ----------
                data
                    The data to compress.

                Returns
                -------
                bytes
                    The compressed data.
                """
                return data


            def decompress(data: bytes) -> bytes:
                """
                Decompress binary data.

                Parameters
                ----------
                data
                    The data to decompress.

                Returns
                -------
                bytes
                    The decompressed data.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-v2-source-title

            Tests source.placement: title config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-source-title",
        "detected_module": "gdtest_source_title",
        "detected_parser": "numpy",
        "export_names": ["compress", "decompress"],
        "num_exports": 2,
    },
}
