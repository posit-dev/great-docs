"""
gdtest_src_google_seealso — src/ layout + Google docstrings + %seealso directive.

Dimensions: A2, D2, E3
Focus: Cross-dimension test combining src/ layout with Google-style docstrings
       and %seealso cross-references.
"""

SPEC = {
    "name": "gdtest_src_google_seealso",
    "description": (
        "src/ layout + Google docstrings + %seealso directive. "
        "Cross-dimension combo testing layout, parser, and directives."
    ),
    "dimensions": ["A2", "D2", "E3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-src-google-seealso",
            "version": "0.1.0",
            "description": "Test package for src layout + Google docs + seealso.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "google",
    },
    "files": {
        "src/gdtest_src_google_seealso/__init__.py": '''\
            """Package with src layout, Google docstrings, and seealso directives."""

            __version__ = "0.1.0"
            __all__ = ["encode", "decode", "compress", "decompress"]
        ''',
        "src/gdtest_src_google_seealso/codec.py": '''\
            """Encoding and compression utilities."""


            def encode(data: str, encoding: str = "utf-8") -> bytes:
                """Encode a string to bytes.

                %seealso decode

                Args:
                    data: The string to encode.
                    encoding: The character encoding to use.

                Returns:
                    The encoded bytes.

                Example:
                    >>> encode("hello")
                    b'hello'
                """
                return data.encode(encoding)


            def decode(data: bytes, encoding: str = "utf-8") -> str:
                """Decode bytes to a string.

                %seealso encode

                Args:
                    data: The bytes to decode.
                    encoding: The character encoding to use.

                Returns:
                    The decoded string.
                """
                return data.decode(encoding)


            def compress(data: bytes, level: int = 6) -> bytes:
                """Compress data using zlib.

                %seealso decompress

                Args:
                    data: The bytes to compress.
                    level: Compression level (1-9).

                Returns:
                    The compressed bytes.
                """
                return data


            def decompress(data: bytes) -> bytes:
                """Decompress zlib-compressed data.

                %seealso compress

                Args:
                    data: The compressed bytes.

                Returns:
                    The decompressed bytes.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-src-google-seealso

            Test package with src/ layout, Google docstrings, and %seealso directives.
        """,
    },
    "expected": {
        "detected_name": "gdtest-src-google-seealso",
        "detected_module": "gdtest_src_google_seealso",
        "detected_parser": "google",
        "export_names": ["compress", "decode", "decompress", "encode"],
        "num_exports": 4,
    },
}
