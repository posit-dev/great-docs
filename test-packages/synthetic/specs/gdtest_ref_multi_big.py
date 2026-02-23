"""
gdtest_ref_multi_big — Multiple big classes in reference config.

Dimensions: P7
Focus: Reference config with two large classes each having 6 methods.
"""

SPEC = {
    "name": "gdtest_ref_multi_big",
    "description": "Multiple big classes in reference config.",
    "dimensions": ["P7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-multi-big",
            "version": "0.1.0",
            "description": "Test reference config with multiple big classes.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Processing",
                "desc": "Data processing",
                "contents": [
                    {"name": "Processor"},
                    {"name": "Transformer"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_multi_big/__init__.py": '"""Test package for multiple big classes in reference config."""\n',
        "gdtest_ref_multi_big/processing.py": '''
            """Data processing classes."""


            class Processor:
                """A data processor for loading, processing, and saving data.

                Parameters
                ----------
                name : str
                    The name of the processor.

                Examples
                --------
                >>> p = Processor("csv")
                >>> p.report()
                {'name': 'csv', 'loaded': False}
                """

                def __init__(self, name: str):
                    """Initialize the processor.

                    Parameters
                    ----------
                    name : str
                        The name of the processor.
                    """
                    self.name = name
                    self._data = None
                    self._loaded = False

                def load(self, source: str) -> None:
                    """Load data from a source.

                    Parameters
                    ----------
                    source : str
                        The path or URI of the data source.

                    Returns
                    -------
                    None

                    Examples
                    --------
                    >>> p = Processor("csv")
                    >>> p.load("data.csv")
                    """
                    self._data = source
                    self._loaded = True

                def process(self) -> list:
                    """Process the loaded data.

                    Returns
                    -------
                    list
                        The processed data as a list.

                    Examples
                    --------
                    >>> p = Processor("csv")
                    >>> p.load("data.csv")
                    >>> p.process()
                    ['data.csv']
                    """
                    return [self._data] if self._data else []

                def validate(self) -> bool:
                    """Validate the loaded data.

                    Returns
                    -------
                    bool
                        True if data is valid, False otherwise.
                    """
                    return self._loaded

                def save(self, destination: str) -> None:
                    """Save processed data to a destination.

                    Parameters
                    ----------
                    destination : str
                        The path to save data to.

                    Returns
                    -------
                    None
                    """
                    pass

                def report(self) -> dict:
                    """Generate a report on the processor state.

                    Returns
                    -------
                    dict
                        A dictionary with the processor status.
                    """
                    return {"name": self.name, "loaded": self._loaded}


            class Transformer:
                """A data transformer for fitting and transforming data.

                Parameters
                ----------
                method : str
                    The transformation method to use.

                Examples
                --------
                >>> t = Transformer("scale")
                >>> t.describe()
                {'method': 'scale', 'fitted': False}
                """

                def __init__(self, method: str):
                    """Initialize the transformer.

                    Parameters
                    ----------
                    method : str
                        The transformation method.
                    """
                    self.method = method
                    self._fitted = False
                    self._params: dict = {}

                def fit(self, data: list) -> None:
                    """Fit the transformer to the data.

                    Parameters
                    ----------
                    data : list
                        The data to fit on.

                    Returns
                    -------
                    None

                    Examples
                    --------
                    >>> t = Transformer("scale")
                    >>> t.fit([1, 2, 3])
                    """
                    self._params = {"min": min(data), "max": max(data)}
                    self._fitted = True

                def transform(self, data: list) -> list:
                    """Transform the data using the fitted parameters.

                    Parameters
                    ----------
                    data : list
                        The data to transform.

                    Returns
                    -------
                    list
                        The transformed data.

                    Examples
                    --------
                    >>> t = Transformer("scale")
                    >>> t.fit([1, 2, 3])
                    >>> t.transform([4, 5])
                    [4, 5]
                    """
                    return data

                def inverse(self, data: list) -> list:
                    """Inverse-transform the data.

                    Parameters
                    ----------
                    data : list
                        The data to inverse-transform.

                    Returns
                    -------
                    list
                        The inverse-transformed data.
                    """
                    return data

                def score(self, data: list) -> float:
                    """Score the data against the fitted model.

                    Parameters
                    ----------
                    data : list
                        The data to score.

                    Returns
                    -------
                    float
                        The score value.
                    """
                    return 1.0 if self._fitted else 0.0

                def describe(self) -> dict:
                    """Describe the transformer state.

                    Returns
                    -------
                    dict
                        A dictionary describing the transformer.
                    """
                    return {"method": self.method, "fitted": self._fitted}
        ''',
        "README.md": (
            "# gdtest-v2-ref-multi-big\n\nTest reference config with multiple big classes.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-multi-big",
        "detected_module": "gdtest_ref_multi_big",
        "detected_parser": "numpy",
        "export_names": ["Processor", "Transformer"],
        "num_exports": 2,
    },
}
