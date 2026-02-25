"""
gdtest_pdm_big_class — PDM layout + big class + NumPy docstrings.

Dimensions: A11, C3, D1
Focus: Cross-dimension test combining PDM build system with a big class
       (>5 methods) and NumPy-style docstrings.
"""

SPEC = {
    "name": "gdtest_pdm_big_class",
    "description": (
        "PDM layout + big class (>5 methods) + NumPy docstrings. "
        "Tests PDM build backend with complex class documentation."
    ),
    "dimensions": ["A11", "C3", "D1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-pdm-big-class",
            "version": "0.1.0",
            "description": "Test package for PDM layout + big class.",
        },
        "build-system": {
            "requires": ["pdm-backend"],
            "build-backend": "pdm.backend",
        },
    },
    "files": {
        "src/gdtest_pdm_big_class/__init__.py": '''\
            """Package with PDM layout and a big class."""

            __version__ = "0.1.0"
            __all__ = ["Pipeline"]
        ''',
        "src/gdtest_pdm_big_class/pipeline.py": '''\
            """Data processing pipeline with many methods."""


            class Pipeline:
                """
                A multi-step data processing pipeline.

                Provides methods for loading, cleaning, transforming,
                validating, aggregating, and exporting data.

                Parameters
                ----------
                name : str
                    The pipeline name.
                verbose : bool
                    Whether to print progress messages.

                Examples
                --------
                >>> p = Pipeline("etl")
                >>> p.load({"items": [1, 2, 3]})
                """

                def __init__(self, name: str, verbose: bool = False):
                    self.name = name
                    self.verbose = verbose
                    self._data = None

                def load(self, source: dict) -> "Pipeline":
                    """
                    Load data from a source dictionary.

                    Parameters
                    ----------
                    source : dict
                        The data source.

                    Returns
                    -------
                    Pipeline
                        Self for method chaining.
                    """
                    self._data = source
                    return self

                def clean(self, drop_nulls: bool = True) -> "Pipeline":
                    """
                    Clean the loaded data.

                    Parameters
                    ----------
                    drop_nulls : bool
                        Whether to drop null values.

                    Returns
                    -------
                    Pipeline
                        Self for method chaining.
                    """
                    return self

                def transform(self, func: callable) -> "Pipeline":
                    """
                    Apply a transformation function to the data.

                    Parameters
                    ----------
                    func : callable
                        A function to apply to each data item.

                    Returns
                    -------
                    Pipeline
                        Self for method chaining.
                    """
                    return self

                def validate(self, schema: dict | None = None) -> bool:
                    """
                    Validate the data against an optional schema.

                    Parameters
                    ----------
                    schema : dict or None
                        Validation schema. If None, performs basic checks.

                    Returns
                    -------
                    bool
                        True if the data passes validation.
                    """
                    return True

                def aggregate(self, group_by: str, agg_func: str = "sum") -> dict:
                    """
                    Aggregate data by a given key.

                    Parameters
                    ----------
                    group_by : str
                        The field to group by.
                    agg_func : str
                        Aggregation function: 'sum', 'mean', 'count'.

                    Returns
                    -------
                    dict
                        Aggregated results.
                    """
                    return {}

                def export(self, fmt: str = "json") -> str:
                    """
                    Export the pipeline results.

                    Parameters
                    ----------
                    fmt : str
                        Output format: 'json', 'csv', or 'parquet'.

                    Returns
                    -------
                    str
                        The serialized output.
                    """
                    return ""

                def status(self) -> dict:
                    """
                    Get the current pipeline status.

                    Returns
                    -------
                    dict
                        Status info including name, data loaded, and step count.
                    """
                    return {"name": self.name, "loaded": self._data is not None}
        ''',
        "README.md": """\
            # gdtest-pdm-big-class

            Test package with PDM build backend and a big class with many methods.
        """,
    },
    "expected": {
        "detected_name": "gdtest-pdm-big-class",
        "detected_module": "gdtest_pdm_big_class",
        "detected_parser": "numpy",
        "export_names": ["Pipeline"],
        "num_exports": 1,
        "big_classes": ["Pipeline"],
    },
}
