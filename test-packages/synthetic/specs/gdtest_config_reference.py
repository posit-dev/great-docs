"""Tests reference config with explicit sections."""

SPEC = {
    "name": "gdtest_config_reference",
    "description": "Tests reference config with explicit titled sections grouping functions.",
    "dimensions": ["K22"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-reference",
            "version": "0.1.0",
            "description": "Test package for reference config with sections.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Core API",
                "desc": "Core functions",
                "contents": [
                    {"name": "compute"},
                    {"name": "analyze"},
                ],
            },
            {
                "title": "Utilities",
                "desc": "Helper utilities",
                "contents": [
                    {"name": "format_result"},
                    {"name": "clean_data"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_config_reference/__init__.py": (
            '"""Test package for reference config with sections."""\n'
            "\n"
            "from gdtest_config_reference.core import compute, analyze\n"
            "from gdtest_config_reference.utils import format_result, clean_data\n"
        ),
        "gdtest_config_reference/core.py": '''
            """Core computation and analysis functions."""


            def compute(x: float, y: float) -> float:
                """Compute the combined value of two numbers.

                Parameters
                ----------
                x : float
                    The first input value.
                y : float
                    The second input value.

                Returns
                -------
                float
                    The computed result.

                Examples
                --------
                >>> compute(3.0, 4.0)
                7.0
                """
                return x + y


            def analyze(data: list) -> dict:
                """Analyze a list of values and return summary statistics.

                Parameters
                ----------
                data : list
                    A list of numeric values to analyze.

                Returns
                -------
                dict
                    A dictionary containing summary statistics such as mean
                    and count.

                Examples
                --------
                >>> analyze([1, 2, 3])
                {'mean': 2.0, 'count': 3}
                """
                if not data:
                    return {"mean": 0.0, "count": 0}
                return {"mean": sum(data) / len(data), "count": len(data)}
        ''',
        "gdtest_config_reference/utils.py": '''
            """Utility functions for formatting and cleaning."""


            def format_result(value: float, precision: int = 2) -> str:
                """Format a numeric result as a string.

                Parameters
                ----------
                value : float
                    The value to format.
                precision : int, optional
                    The number of decimal places, by default 2.

                Returns
                -------
                str
                    The formatted string representation.

                Examples
                --------
                >>> format_result(3.14159, precision=3)
                '3.142'
                """
                return f"{value:.{precision}f}"


            def clean_data(raw: list) -> list:
                """Clean a list of raw data by removing None values.

                Parameters
                ----------
                raw : list
                    The raw data list, possibly containing None values.

                Returns
                -------
                list
                    A cleaned list with None values removed.

                Examples
                --------
                >>> clean_data([1, None, 3, None, 5])
                [1, 3, 5]
                """
                return [x for x in raw if x is not None]
        ''',
    },
    "expected": {
        "files_exist": [
            "great-docs/reference/index.html",
            "great-docs/reference/compute.html",
            "great-docs/reference/analyze.html",
            "great-docs/reference/format_result.html",
            "great-docs/reference/clean_data.html",
        ],
        "files_contain": {
            "great-docs/reference/index.html": ["Core API", "Utilities"],
        },
    },
}
