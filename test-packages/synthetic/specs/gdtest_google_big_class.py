"""
gdtest_google_big_class — Google docstrings + big class.

Dimensions: A1, B1, C3, D2, E6, F6, G1, H7
Focus: Big class with all methods documented in Google style to verify
       Google docstring parsing works with the big-class method extraction.
"""

SPEC = {
    "name": "gdtest_google_big_class",
    "description": "Google docstrings with a big class (>5 methods)",
    "dimensions": ["A1", "B1", "C3", "D2", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-google-big-class",
            "version": "0.1.0",
            "description": "Test Google docstrings with big class method extraction",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_google_big_class/__init__.py": '''\
            """Package with a big class using Google-style docstrings."""

            __version__ = "0.1.0"
            __all__ = ["DataProcessor", "load_data"]


            class DataProcessor:
                """A processor for tabular data.

                Args:
                    source: Data source path.
                    format: Data format string.
                """

                def __init__(self, source: str, format: str = "csv"):
                    self.source = source
                    self.format = format

                def load(self) -> list:
                    """Load data from the source.

                    Returns:
                        A list of records.
                    """
                    return []

                def filter(self, predicate) -> "DataProcessor":
                    """Filter data using a predicate function.

                    Args:
                        predicate: A callable that returns True for items to keep.

                    Returns:
                        A new DataProcessor with filtered data.
                    """
                    return self

                def sort(self, key: str, reverse: bool = False) -> "DataProcessor":
                    """Sort data by a key.

                    Args:
                        key: Column name to sort by.
                        reverse: If True, sort in descending order.

                    Returns:
                        A new DataProcessor with sorted data.
                    """
                    return self

                def aggregate(self, column: str, func: str = "sum") -> dict:
                    """Aggregate values in a column.

                    Args:
                        column: Column to aggregate.
                        func: Aggregation function name.

                    Returns:
                        Dictionary with aggregation results.
                    """
                    return {}

                def export(self, path: str, format: str = "csv") -> None:
                    """Export data to a file.

                    Args:
                        path: Output file path.
                        format: Output format.
                    """
                    pass

                def describe(self) -> dict:
                    """Generate summary statistics.

                    Returns:
                        Dictionary of column statistics.
                    """
                    return {}

                def head(self, n: int = 5) -> list:
                    """Return the first n records.

                    Args:
                        n: Number of records to return.

                    Returns:
                        List of the first n records.
                    """
                    return []


            def load_data(path: str) -> DataProcessor:
                """Load data from a file into a DataProcessor.

                Args:
                    path: Path to the data file.

                Returns:
                    A DataProcessor instance with the loaded data.
                """
                return DataProcessor(path)
        ''',
        "README.md": """\
            # gdtest-google-big-class

            Tests Google docstring parsing with big class method extraction.
        """,
    },
    "expected": {
        "detected_name": "gdtest-google-big-class",
        "detected_module": "gdtest_google_big_class",
        "detected_parser": "google",
        "export_names": ["DataProcessor", "load_data"],
        "num_exports": 2,
        "section_titles": ["Classes", "DataProcessor Methods", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
