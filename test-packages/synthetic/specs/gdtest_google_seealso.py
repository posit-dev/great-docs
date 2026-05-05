"""
gdtest_google_seealso — Google docstrings + %seealso directives.

Dimensions: A1, B1, C1, D2, E3, F6, G1, H7
Focus: Google-style docstrings with %seealso cross-references to verify
       both render together correctly.
"""

SPEC = {
    "name": "gdtest_google_seealso",
    "description": "Google docstrings with %seealso cross-references",
    "dimensions": ["A1", "B1", "C1", "D2", "E3", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-google-seealso",
            "version": "0.1.0",
            "description": "Test Google docstrings with %seealso",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_google_seealso/__init__.py": '''\
            """Package with Google docstrings and %seealso directives."""

            __version__ = "0.1.0"
            __all__ = ["encode", "decode", "compress", "decompress"]


            def encode(data: str) -> bytes:
                """Encode a string to bytes.

                %seealso decode

                Args:
                    data: The string to encode.

                Returns:
                    Encoded bytes.
                """
                return data.encode()


            def decode(data: bytes) -> str:
                """Decode bytes to a string.

                %seealso encode

                Args:
                    data: The bytes to decode.

                Returns:
                    Decoded string.
                """
                return data.decode()


            def compress(data: bytes) -> bytes:
                """Compress bytes data.

                %seealso decompress

                Args:
                    data: The bytes to compress.

                Returns:
                    Compressed bytes.
                """
                return data


            def decompress(data: bytes) -> bytes:
                """Decompress bytes data.

                %seealso compress

                Args:
                    data: The bytes to decompress.

                Returns:
                    Decompressed bytes.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-google-seealso

            Tests Google docstrings with %seealso cross-references.
        """,
    },
    "expected": {
        "detected_name": "gdtest-google-seealso",
        "detected_module": "gdtest_google_seealso",
        "detected_parser": "google",
        "export_names": ["encode", "decode", "compress", "decompress"],
        "num_exports": 4,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
