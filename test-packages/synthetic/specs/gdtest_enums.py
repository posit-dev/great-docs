"""
gdtest_enums — enum.Enum subclasses.

Dimensions: A1, B1, C6, D1, E6, F6, G1, H7
Focus: 2 enums — one Enum, one IntEnum.
       Tests enum member listing and value documentation.
"""

SPEC = {
    "name": "gdtest_enums",
    "description": "Enum subclasses (Enum + IntEnum)",
    "dimensions": ["A1", "B1", "C6", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-enums",
            "version": "0.1.0",
            "description": "A synthetic test package with enums",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_enums/__init__.py": '''\
            """A test package with enum objects."""

            __version__ = "0.1.0"
            __all__ = ["Color", "Priority"]

            from enum import Enum, IntEnum


            class Color(Enum):
                """
                Available colors for styling.

                Each color maps to a CSS-compatible color name.
                """
                RED = "red"
                GREEN = "green"
                BLUE = "blue"
                YELLOW = "yellow"


            class Priority(IntEnum):
                """
                Task priority levels.

                Higher values indicate higher priority.
                """
                LOW = 1
                MEDIUM = 2
                HIGH = 3
                CRITICAL = 4
        ''',
        "README.md": """\
            # gdtest-enums

            A synthetic test package with ``enum.Enum`` subclasses.
        """,
    },
    "expected": {
        "detected_name": "gdtest-enums",
        "detected_module": "gdtest_enums",
        "detected_parser": "numpy",
        "export_names": ["Color", "Priority"],
        "num_exports": 2,
        "section_titles": ["Enumerations"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
