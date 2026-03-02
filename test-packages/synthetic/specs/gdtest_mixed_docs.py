"""
gdtest_mixed_docs — Mixed docstring styles within one package.

Dimensions: A1, B1, C4, D5, E6, F6, G1, H7
Focus: 4 functions — 2 with NumPy docstrings, 2 with Google docstrings.
       Tests style-detection majority vote and consistent parser choice.
"""

SPEC = {
    "name": "gdtest_mixed_docs",
    "description": "Mixed docstring styles (NumPy + Google); transform is %nodoc and should not appear",
    "dimensions": ["A1", "B1", "C4", "D5", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-mixed-docs",
            "version": "0.1.0",
            "description": "A synthetic test package with mixed docstring styles",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_mixed_docs/__init__.py": '''\
            """A package with mixed NumPy and Google docstrings."""

            __version__ = "0.1.0"
            __all__ = ["Converter", "encode", "decode", "validate", "transform"]


            class Converter:
                """
                A data converter.

                Parameters
                ----------
                fmt
                    The output format.
                """

                def __init__(self, fmt: str = "json"):
                    self.fmt = fmt

                def convert(self, data: str) -> str:
                    """
                    Convert data to the target format.

                    Parameters
                    ----------
                    data
                        The input data string.

                    Returns
                    -------
                    str
                        Converted data.
                    """
                    return data


            def encode(data: str, encoding: str = "utf-8") -> bytes:
                """
                Encode a string to bytes.

                Parameters
                ----------
                data
                    The string to encode.
                encoding
                    The target encoding.

                Returns
                -------
                bytes
                    The encoded bytes.
                """
                return data.encode(encoding)


            def decode(data: bytes, encoding: str = "utf-8") -> str:
                """
                Decode bytes to a string.

                Parameters
                ----------
                data
                    The bytes to decode.
                encoding
                    The source encoding.

                Returns
                -------
                str
                    The decoded string.
                """
                return data.decode(encoding)


            def validate(data: str) -> bool:
                """Validate the input data.

                Args:
                    data: The data string to validate.

                Returns:
                    True if the data is valid.
                """
                return len(data) > 0


            def transform(data: str, upper: bool = False) -> str:
                """Transform the input data.

                %nodoc

                Args:
                    data: The data string to transform.
                    upper: If True, convert to uppercase.

                Returns:
                    The transformed data string.
                """
                return data.upper() if upper else data
        ''',
        "README.md": """\
            # gdtest-mixed-docs

            A synthetic test package with mixed NumPy and Google docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-mixed-docs",
        "detected_module": "gdtest_mixed_docs",
        "detected_parser": "numpy",
        "export_names": ["Converter", "encode", "decode", "validate", "transform"],
        "num_exports": 5,
        "nodoc_items": ['transform'],
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
