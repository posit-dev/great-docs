"""
gdtest_sphinx_exc_role — :py:exc: cross-reference roles.

Dimensions: L12
Focus: Two functions with :py:exc:`ValueError` and :py:exc:`TypeError`
       references in their descriptions and Raises sections.
"""

SPEC = {
    "name": "gdtest_sphinx_exc_role",
    "description": ":py:exc: cross-reference roles for exceptions",
    "dimensions": ["L12"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sphinx-exc-role",
            "version": "0.1.0",
            "description": "Test :py:exc: Sphinx role rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_sphinx_exc_role/__init__.py": '''\
            """Package demonstrating :py:exc: cross-reference roles."""

            __version__ = "0.1.0"
            __all__ = ["parse_int", "safe_cast"]


            def parse_int(text: str) -> int:
                """
                Parse a string into an integer.

                Raises :py:exc:`ValueError` if not numeric.

                Parameters
                ----------
                text
                    The string to parse.

                Returns
                -------
                int
                    The parsed integer value.

                Raises
                ------
                ValueError
                    If the string cannot be parsed as an integer.
                """
                return int(text)


            def safe_cast(value: object, target_type: type) -> object:
                """
                Safely cast a value to a target type.

                May raise :py:exc:`TypeError` or :py:exc:`ValueError`.

                Parameters
                ----------
                value
                    The value to cast.
                target_type
                    The type to cast to.

                Returns
                -------
                object
                    The cast value.

                Raises
                ------
                TypeError
                    If the value cannot be cast to the target type.
                ValueError
                    If the value is invalid for the target type.
                """
                return target_type(value)
        ''',
        "README.md": """\
            # gdtest-v2-sphinx-exc-role

            A synthetic test package testing ``:py:exc:`` cross-reference roles.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sphinx-exc-role",
        "detected_module": "gdtest_sphinx_exc_role",
        "detected_parser": "numpy",
        "export_names": ["parse_int", "safe_cast"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
