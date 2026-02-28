"""
gdtest_big_class — Class with >5 public methods.

Dimensions: A1, B1, C3, D1, E6, F6, G1, H7
Focus: One class with 8 methods plus 2 standalone functions.
       Tests the method-section threshold: classes with >5 methods should get
       `members: []` in the config and a separate "ClassName Methods" section.
"""

SPEC = {
    "name": "gdtest_big_class",
    "description": "Class with >5 public methods triggers separate method section",
    "dimensions": ["A1", "B1", "C3", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-big-class",
            "version": "0.1.0",
            "description": "A package with a class that has many methods",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_big_class/__init__.py": '''\
            """Package with a large class to test method-section generation."""

            __version__ = "0.1.0"
            __all__ = ["DataProcessor", "load_data", "save_data"]


            class DataProcessor:
                """
                A data processing pipeline with many operations.

                Parameters
                ----------
                name
                    The name of this processor instance.

                Examples
                --------
                >>> dp = DataProcessor("etl")
                >>> dp.name
                'etl'
                """

                def __init__(self, name: str):
                    self.name = name
                    self._data = None

                def load(self, path: str) -> None:
                    """
                    Load data from a file path.

                    Parameters
                    ----------
                    path
                        Path to the data file.
                    """
                    self._data = path

                def transform(self, func) -> "DataProcessor":
                    """
                    Apply a transformation function to the data.

                    Parameters
                    ----------
                    func
                        A callable that transforms the data.

                    Returns
                    -------
                    DataProcessor
                        Self, for method chaining.
                    """
                    return self

                def filter(self, predicate) -> "DataProcessor":
                    """
                    Filter data based on a predicate.

                    Parameters
                    ----------
                    predicate
                        A callable returning True for rows to keep.

                    Returns
                    -------
                    DataProcessor
                        Self, for method chaining.
                    """
                    return self

                def sort(self, key: str, ascending: bool = True) -> "DataProcessor":
                    """
                    Sort data by a key.

                    Parameters
                    ----------
                    key
                        The column/field to sort by.
                    ascending
                        Sort ascending if True, descending if False.

                    Returns
                    -------
                    DataProcessor
                        Self, for method chaining.
                    """
                    return self

                def aggregate(self, func, column: str) -> "DataProcessor":
                    """
                    Aggregate data by applying a function to a column.

                    Parameters
                    ----------
                    func
                        Aggregation function (e.g., sum, mean).
                    column
                        Column to aggregate.

                    Returns
                    -------
                    DataProcessor
                        Self, for method chaining.
                    """
                    return self

                def validate(self) -> bool:
                    """
                    Validate the current data state.

                    Returns
                    -------
                    bool
                        True if data is valid.
                    """
                    return self._data is not None

                def export(self, path: str, fmt: str = "csv") -> None:
                    """
                    Export data to a file.

                    Parameters
                    ----------
                    path
                        Output file path.
                    fmt
                        Output format (csv, json, parquet).
                    """
                    pass

                def summary(self) -> dict:
                    """
                    Return a summary of the data.

                    Returns
                    -------
                    dict
                        A dictionary with summary statistics.
                    """
                    return {"name": self.name, "has_data": self._data is not None}


            def load_data(path: str) -> DataProcessor:
                """
                Convenience function to create a processor and load data.

                Parameters
                ----------
                path
                    Path to the data file.

                Returns
                -------
                DataProcessor
                    A new processor with data loaded.
                """
                dp = DataProcessor("default")
                dp.load(path)
                return dp


            def save_data(processor: DataProcessor, path: str) -> None:
                """
                Save processor data to a file.

                Parameters
                ----------
                processor
                    The data processor whose data to save.
                path
                    Output file path.
                """
                processor.export(path)
        ''',
        "README.md": """\
            # gdtest-big-class

            Package with a class that has >5 methods, testing separate method
            section generation in Great Docs.
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-big-class",
        "detected_module": "gdtest_big_class",
        "detected_parser": "numpy",
        "export_names": ["DataProcessor", "load_data", "save_data"],
        "num_exports": 3,
        "section_titles": ["Classes", "DataProcessor Methods", "Functions"],
        "big_class_name": "DataProcessor",
        "big_class_method_count": 8,
        "has_user_guide": False,
    },
}
