"""
gdtest_all_concat — __all__ concatenation from submodules.

Dimensions: A1, B2, C4, D1, E6, F6, G1, H7
Focus: __all__ is built by concatenating sub-module __all__ lists
       (e.g., __all__ = _models.__all__ + _utils.__all__). Because this
       is not a literal list, the AST parser cannot extract it and the
       system must fall back to griffe-based discovery. Tests that the
       resulting exports are still correct.
"""

SPEC = {
    "name": "gdtest_all_concat",
    "description": "__all__ built by concatenating sub-module __all__ lists",
    "dimensions": ["A1", "B2", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-all-concat",
            "version": "0.1.0",
            "description": "A synthetic test package testing __all__ concatenation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_all_concat/__init__.py": '''\
            """A test package with __all__ concatenation from submodules."""

            __version__ = "0.1.0"

            from ._models import Record, validate_record
            from ._utils import format_output, parse_input

            __all__ = _models.__all__ + _utils.__all__
        ''',
        "gdtest_all_concat/_models.py": '''\
            """Model classes and validation."""

            __all__ = ["Record", "validate_record"]


            class Record:
                """
                A data record.

                Parameters
                ----------
                name
                    The record name.
                value
                    The record value.
                """

                def __init__(self, name: str, value: int = 0):
                    self.name = name
                    self.value = value

                def to_dict(self) -> dict:
                    """
                    Convert the record to a dictionary.

                    Returns
                    -------
                    dict
                        Dictionary with name and value keys.
                    """
                    return {"name": self.name, "value": self.value}


            def validate_record(record: "Record") -> bool:
                """
                Validate a record.

                Parameters
                ----------
                record
                    The record to validate.

                Returns
                -------
                bool
                    True if the record is valid.
                """
                return bool(record.name)
        ''',
        "gdtest_all_concat/_utils.py": '''\
            """Utility functions for input/output."""

            __all__ = ["format_output", "parse_input"]


            def format_output(data: dict) -> str:
                """
                Format output data as a string.

                Parameters
                ----------
                data
                    The data to format.

                Returns
                -------
                str
                    Formatted string representation.
                """
                return str(data)


            def parse_input(text: str) -> dict:
                """
                Parse input text into a dictionary.

                Parameters
                ----------
                text
                    The input text to parse.

                Returns
                -------
                dict
                    Parsed data.
                """
                return {"raw": text}
        ''',
        "README.md": """\
            # gdtest-all-concat

            A synthetic test package testing ``__all__`` concatenation from submodules.
        """,
    },
    "expected": {
        "detected_name": "gdtest-all-concat",
        "detected_module": "gdtest_all_concat",
        "detected_parser": "numpy",
        "export_names": ["Record", "validate_record", "format_output", "parse_input"],
        "num_exports": 4,
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'sechdg', 'sbsec'],
},
}
