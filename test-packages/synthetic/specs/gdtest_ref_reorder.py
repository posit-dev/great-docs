"""
gdtest_ref_reorder — Reference config reordering: Functions before Classes.

Dimensions: P4
Focus: Reference config that places function sections before class sections.
"""

SPEC = {
    "name": "gdtest_ref_reorder",
    "description": "Reference config reordering: Functions before Classes.",
    "dimensions": ["P4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-reorder",
            "version": "0.1.0",
            "description": "Test reference config reordering.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Functions",
                "desc": "Utility functions",
                "contents": [
                    {"name": "compute"},
                    {"name": "transform"},
                ],
            },
            {
                "title": "Classes",
                "desc": "Data classes",
                "contents": [
                    {"name": "DataModel"},
                    {"name": "Schema"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_reorder/__init__.py": '"""Test package for reference config reordering."""\n',
        "gdtest_ref_reorder/functions.py": '''
            """Utility functions for computing and transforming."""


            def compute(x: float) -> float:
                """Compute the square of a value.

                Parameters
                ----------
                x : float
                    The input value.

                Returns
                -------
                float
                    The squared value.

                Examples
                --------
                >>> compute(3.0)
                9.0
                """
                return x ** 2


            def transform(data: list) -> list:
                """Transform a list by doubling each element.

                Parameters
                ----------
                data : list
                    The input data list.

                Returns
                -------
                list
                    The transformed data with doubled values.

                Examples
                --------
                >>> transform([1, 2, 3])
                [2, 4, 6]
                """
                return [x * 2 for x in data]
        ''',
        "gdtest_ref_reorder/models.py": '''
            """Data model and schema classes."""


            class DataModel:
                """A data model for holding and validating data.

                Parameters
                ----------
                data : dict
                    The data to model.

                Examples
                --------
                >>> m = DataModel({"key": "value"})
                >>> m.validate()
                True
                """

                def __init__(self, data: dict):
                    """Initialize the data model.

                    Parameters
                    ----------
                    data : dict
                        The data to model.
                    """
                    self.data = data

                def validate(self) -> bool:
                    """Validate the data model.

                    Returns
                    -------
                    bool
                        True if the data is valid.
                    """
                    return bool(self.data)


            class Schema:
                """A schema for parsing and validating structured data.

                Parameters
                ----------
                definition : dict
                    The schema definition.

                Examples
                --------
                >>> s = Schema({"type": "object"})
                >>> s.parse({"key": "value"})
                {'key': 'value'}
                """

                def __init__(self, definition: dict):
                    """Initialize the schema.

                    Parameters
                    ----------
                    definition : dict
                        The schema definition.
                    """
                    self.definition = definition

                def parse(self, data: dict) -> dict:
                    """Parse data according to the schema.

                    Parameters
                    ----------
                    data : dict
                        The data to parse.

                    Returns
                    -------
                    dict
                        The parsed data.
                    """
                    return data
        ''',
        "README.md": ("# gdtest-v2-ref-reorder\n\nTest reference config reordering.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-reorder",
        "detected_module": "gdtest_ref_reorder",
        "detected_parser": "numpy",
        "export_names": ["DataModel", "Schema", "compute", "transform"],
        "num_exports": 4,
    },
}
