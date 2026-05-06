"""
gdtest_seealso — %seealso cross-references.

Dimensions: A1, B1, C4, D1, E3, F6, G1, H7
Focus: 3 related functions, each referencing the others with %seealso.
       Tests cross-reference generation in rendered docs.
"""

SPEC = {
    "name": "gdtest_seealso",
    "description": "%seealso cross-references between functions",
    "dimensions": ["A1", "B1", "C4", "D1", "E3", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-seealso",
            "version": "0.1.0",
            "description": "A synthetic test package testing %seealso",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_seealso/__init__.py": '''\
            """Package demonstrating %seealso cross-references."""

            __version__ = "0.1.0"
            __all__ = ["Encoder", "encode", "decode", "validate"]


            class Encoder:
                """
                An encoder/decoder pair.

                %seealso encode, decode

                Parameters
                ----------
                codec
                    The codec to use.
                """

                def __init__(self, codec: str = "utf-8"):
                    self.codec = codec

                def process(self, data: str) -> bytes:
                    """
                    Encode the data.

                    Parameters
                    ----------
                    data
                        Input string.

                    Returns
                    -------
                    bytes
                        Encoded bytes.
                    """
                    return data.encode(self.codec)


            def encode(data: str, codec: str = "utf-8") -> bytes:
                """
                Encode a string to bytes.

                %seealso decode, validate

                Parameters
                ----------
                data
                    The string to encode.
                codec
                    The codec to use.

                Returns
                -------
                bytes
                    The encoded bytes.
                """
                return data.encode(codec)


            def decode(data: bytes, codec: str = "utf-8") -> str:
                """
                Decode bytes to a string.

                %seealso encode, validate

                Parameters
                ----------
                data
                    The bytes to decode.
                codec
                    The codec to use.

                Returns
                -------
                str
                    The decoded string.
                """
                return data.decode(codec)


            def validate(data: str | bytes) -> bool:
                """
                Validate that data can be encoded/decoded.

                %seealso encode, decode

                Parameters
                ----------
                data
                    The data to validate.

                Returns
                -------
                bool
                    True if valid.
                """
                return isinstance(data, (str, bytes))
        ''',
        "README.md": """\
            # gdtest-seealso

            A synthetic test package testing ``%seealso`` cross-references.
        """,
    },
    "expected": {
        "detected_name": "gdtest-seealso",
        "detected_module": "gdtest_seealso",
        "detected_parser": "numpy",
        "export_names": ["Encoder", "encode", "decode", "validate"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "seealso": {
            "encode": ["decode", "validate"],
            "decode": ["encode", "validate"],
            "validate": ["encode", "decode"],
        },
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
