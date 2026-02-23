"""
gdtest_sphinx_func_role — :py:func: cross-reference roles.

Dimensions: L10
Focus: 3 functions that cross-reference each other using :py:func:`name`
       in their docstrings. Tests that Sphinx func roles render correctly.
"""

SPEC = {
    "name": "gdtest_sphinx_func_role",
    "description": ":py:func: cross-reference roles between functions",
    "dimensions": ["L10"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sphinx-func-role",
            "version": "0.1.0",
            "description": "Test :py:func: Sphinx role rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_sphinx_func_role/__init__.py": '''\
            """Package demonstrating :py:func: cross-reference roles."""

            __version__ = "0.1.0"
            __all__ = ["encode", "decode", "validate"]


            def encode(data: str) -> bytes:
                """
                Encode a string to bytes.

                See also :py:func:`decode` for the reverse.

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
                Decode bytes back to a string.

                See also :py:func:`encode`.

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


            def validate(data: str) -> bool:
                """
                Validate that a string can be encoded.

                Call :py:func:`encode` first.

                Parameters
                ----------
                data
                    The string to validate.

                Returns
                -------
                bool
                    True if the string is valid for encoding.
                """
                try:
                    data.encode("utf-8")
                    return True
                except (UnicodeEncodeError, AttributeError):
                    return False
        ''',
        "README.md": """\
            # gdtest-v2-sphinx-func-role

            A synthetic test package testing ``:py:func:`` cross-reference roles.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sphinx-func-role",
        "detected_module": "gdtest_sphinx_func_role",
        "detected_parser": "numpy",
        "export_names": ["encode", "decode", "validate"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
