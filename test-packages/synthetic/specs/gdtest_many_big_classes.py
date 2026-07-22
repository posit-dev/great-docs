"""
gdtest_many_big_classes — Five big classes each with 6+ methods.

Dimensions: A1, B1, C3, D1, E6, F6, G1, H7
Focus: Multiple big classes in one module to test that each gets its
       own method subsection without name collisions.
"""

SPEC = {
    "name": "gdtest_many_big_classes",
    "description": "Five big classes with 6+ methods each",
    "dimensions": ["A1", "B1", "C3", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-many-big-classes",
            "version": "0.1.0",
            "description": "Test multiple big classes in one module",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_many_big_classes/__init__.py": '''\
            """Package with five big classes."""

            __version__ = "0.1.0"
            __all__ = [
                "Processor",
                "Transformer",
                "Validator",
                "Formatter",
                "Exporter",
            ]


            class Processor:
                """
                Data processor with many operations.

                Parameters
                ----------
                source
                    Data source path.
                """

                def __init__(self, source: str):
                    self.source = source

                def load(self) -> list:
                    """Load data."""
                    return []

                def filter(self, pred) -> list:
                    """Filter data by predicate."""
                    return []

                def sort(self, key: str) -> list:
                    """Sort data by key."""
                    return []

                def group(self, key: str) -> dict:
                    """Group data by key."""
                    return {}

                def merge(self, other: list) -> list:
                    """Merge with other data."""
                    return []

                def deduplicate(self) -> list:
                    """Remove duplicates."""
                    return []


            class Transformer:
                """
                Data transformer with many conversions.

                Parameters
                ----------
                config
                    Transformation config.
                """

                def __init__(self, config: dict):
                    self.config = config

                def to_json(self, data) -> str:
                    """Convert to JSON."""
                    return ""

                def to_csv(self, data) -> str:
                    """Convert to CSV."""
                    return ""

                def to_xml(self, data) -> str:
                    """Convert to XML."""
                    return ""

                def from_json(self, text: str) -> dict:
                    """Parse from JSON."""
                    return {}

                def from_csv(self, text: str) -> list:
                    """Parse from CSV."""
                    return []

                def normalize(self, data) -> dict:
                    """Normalize data structure."""
                    return {}


            class Validator:
                """
                Data validator with many checks.

                Parameters
                ----------
                schema
                    Validation schema.
                """

                def __init__(self, schema: dict):
                    self.schema = schema

                def check_types(self, data: dict) -> bool:
                    """Check value types."""
                    return True

                def check_required(self, data: dict) -> bool:
                    """Check required fields."""
                    return True

                def check_ranges(self, data: dict) -> bool:
                    """Check numeric ranges."""
                    return True

                def check_patterns(self, data: dict) -> bool:
                    """Check string patterns."""
                    return True

                def check_uniqueness(self, data: list) -> bool:
                    """Check uniqueness constraints."""
                    return True

                def validate_all(self, data) -> dict:
                    """Run all validations."""
                    return {"valid": True}


            class Formatter:
                """
                Output formatter with many styles.

                Parameters
                ----------
                style
                    Format style name.
                """

                def __init__(self, style: str = "default"):
                    self.style = style

                def as_table(self, data: list) -> str:
                    """Format as ASCII table."""
                    return ""

                def as_markdown(self, data: list) -> str:
                    """Format as Markdown."""
                    return ""

                def as_html(self, data: list) -> str:
                    """Format as HTML."""
                    return ""

                def as_latex(self, data: list) -> str:
                    """Format as LaTeX."""
                    return ""

                def as_plain(self, data: list) -> str:
                    """Format as plain text."""
                    return ""

                def set_style(self, style: str) -> None:
                    """Change the format style."""
                    self.style = style


            class Exporter:
                """
                Data exporter with many targets.

                Parameters
                ----------
                destination
                    Export destination path.
                """

                def __init__(self, destination: str):
                    self.destination = destination

                def to_file(self, data, path: str) -> None:
                    """Export to a file."""
                    pass

                def to_database(self, data, conn_str: str) -> None:
                    """Export to a database."""
                    pass

                def to_api(self, data, endpoint: str) -> dict:
                    """Export via API call."""
                    return {}

                def to_stream(self, data) -> bytes:
                    """Export as byte stream."""
                    return b""

                def to_clipboard(self, data) -> None:
                    """Export to clipboard."""
                    pass

                def to_email(self, data, recipient: str) -> None:
                    """Export via email."""
                    pass
        ''',
        "README.md": """\
            # gdtest-many-big-classes

            Tests five big classes in one module, each with its own method section.
        """,
    },
    "expected": {
        "detected_name": "gdtest-many-big-classes",
        "detected_module": "gdtest_many_big_classes",
        "detected_parser": "numpy",
        "export_names": [
            "Processor",
            "Transformer",
            "Validator",
            "Formatter",
            "Exporter",
        ],
        "num_exports": 5,
        "section_titles": [
            "Classes",
            "Processor Methods",
            "Transformer Methods",
            "Validator Methods",
            "Formatter Methods",
            "Exporter Methods",
        ],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
