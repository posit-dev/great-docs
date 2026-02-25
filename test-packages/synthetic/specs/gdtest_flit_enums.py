"""
gdtest_flit_enums — Flit layout + enums + Google docstrings.

Dimensions: A10, C6, D2
Focus: Cross-dimension test combining Flit build backend with enum types
       and Google-style docstrings.
"""

SPEC = {
    "name": "gdtest_flit_enums",
    "description": (
        "Flit layout + enums + Google docstrings. "
        "Tests Flit build backend with enum type documentation."
    ),
    "dimensions": ["A10", "C6", "D2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-flit-enums",
            "version": "0.1.0",
            "description": "Test package for Flit layout + enums.",
        },
        "build-system": {
            "requires": ["flit_core>=3.2"],
            "build-backend": "flit_core.buildapi",
        },
    },
    "config": {
        "parser": "google",
    },
    "files": {
        "gdtest_flit_enums/__init__.py": '''\
            """Package with Flit layout and enums using Google docstrings."""

            __version__ = "0.1.0"
            __all__ = ["Color", "Status", "Priority", "get_label"]
        ''',
        "gdtest_flit_enums/types.py": '''\
            """Enum types for the application."""

            from enum import Enum, auto


            class Color(Enum):
                """Available color options.

                Each color maps to an RGB hex string value.

                Attributes:
                    RED: Bright red (#FF0000).
                    GREEN: Bright green (#00FF00).
                    BLUE: Bright blue (#0000FF).
                    YELLOW: Bright yellow (#FFFF00).
                """

                RED = "#FF0000"
                GREEN = "#00FF00"
                BLUE = "#0000FF"
                YELLOW = "#FFFF00"


            class Status(Enum):
                """Task lifecycle status.

                Tracks the progression of a task from creation to completion.

                Attributes:
                    PENDING: Task has been created but not started.
                    RUNNING: Task is currently executing.
                    COMPLETED: Task finished successfully.
                    FAILED: Task encountered an error.
                """

                PENDING = auto()
                RUNNING = auto()
                COMPLETED = auto()
                FAILED = auto()


            class Priority(Enum):
                """Task priority levels.

                Higher numeric values indicate greater urgency.

                Attributes:
                    LOW: Low priority (1).
                    MEDIUM: Medium priority (2).
                    HIGH: High priority (3).
                    CRITICAL: Critical priority (4).
                """

                LOW = 1
                MEDIUM = 2
                HIGH = 3
                CRITICAL = 4


            def get_label(status: Status) -> str:
                """Get a human-readable label for a status.

                Args:
                    status: The status enum value.

                Returns:
                    A formatted label string.

                Example:
                    >>> get_label(Status.RUNNING)
                    'In Progress'
                """
                labels = {
                    Status.PENDING: "Waiting",
                    Status.RUNNING: "In Progress",
                    Status.COMPLETED: "Done",
                    Status.FAILED: "Error",
                }
                return labels.get(status, "Unknown")
        ''',
        "README.md": """\
            # gdtest-flit-enums

            Test package with Flit build backend, enum types, and Google docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-flit-enums",
        "detected_module": "gdtest_flit_enums",
        "detected_parser": "google",
        "export_names": ["Color", "Priority", "Status", "get_label"],
        "num_exports": 4,
    },
}
