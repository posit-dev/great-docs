"""
gdtest_numpy_rich — Rich NumPy-style docstrings with ALL sections.

Dimensions: L15
Focus: Two functions with comprehensive NumPy docstring sections including
       Parameters, Returns, Raises, See Also, Notes, Warnings, References,
       and Examples.
"""

SPEC = {
    "name": "gdtest_numpy_rich",
    "description": "Rich NumPy-style docstrings with all sections",
    "dimensions": ["L15"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-numpy-rich",
            "version": "0.1.0",
            "description": "Test rich NumPy docstring section rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "numpy",
    },
    "files": {
        "gdtest_numpy_rich/__init__.py": '''\
            """Package with rich NumPy-style docstrings."""

            __version__ = "0.1.0"
            __all__ = ["analyze", "transform"]


            def analyze(data: list, method: str = "mean") -> dict:
                r"""
                Analyze a dataset using the specified method.

                Computes summary statistics on the input data using the
                chosen aggregation method. The result includes the computed
                value and metadata about the analysis.

                Parameters
                ----------
                data
                    A list of numeric values to analyze.
                method
                    The aggregation method to use. One of ``"mean"``,
                    ``"median"``, or ``"sum"``. Defaults to ``"mean"``.

                Returns
                -------
                dict
                    A dictionary with keys ``"value"`` (the computed result),
                    ``"method"`` (the method used), and ``"count"`` (number
                    of data points).

                Raises
                ------
                ValueError
                    If ``data`` is empty or ``method`` is not recognized.
                TypeError
                    If ``data`` contains non-numeric values.

                See Also
                --------
                transform : Transform data before analysis.

                Notes
                -----
                The mean is computed as the arithmetic mean. For large datasets,
                consider using chunked processing to avoid memory issues.

                The implementation uses a simple single-pass algorithm:

                .. math::

                    \\bar{x} = \\frac{1}{n} \\sum_{i=1}^{n} x_i

                Warnings
                --------
                This function loads all data into memory. For datasets larger
                than available RAM, use a streaming approach instead.

                References
                ----------
                .. [1] Knuth, D. "The Art of Computer Programming", Vol 2.
                .. [2] https://en.wikipedia.org/wiki/Arithmetic_mean

                Examples
                --------
                >>> analyze([1, 2, 3, 4, 5])
                {'value': 3.0, 'method': 'mean', 'count': 5}

                >>> analyze([10, 20, 30], method="sum")
                {'value': 60, 'method': 'sum', 'count': 3}
                """
                if not data:
                    raise ValueError("data must not be empty")

                if method == "mean":
                    value = sum(data) / len(data)
                elif method == "median":
                    sorted_data = sorted(data)
                    mid = len(sorted_data) // 2
                    value = sorted_data[mid]
                elif method == "sum":
                    value = sum(data)
                else:
                    raise ValueError(f"Unknown method: {method}")

                return {"value": value, "method": method, "count": len(data)}


            def transform(data: list, scale: float = 1.0) -> list:
                """
                Transform a list of values by applying a scaling factor.

                Each element in the input list is multiplied by the scale
                factor to produce the output list.

                Parameters
                ----------
                data
                    A list of numeric values to transform.
                scale
                    The scaling factor to apply. Defaults to ``1.0``.

                Returns
                -------
                list
                    A new list with each element scaled.

                Notes
                -----
                The transformation is applied element-wise. The original
                list is not modified.

                Examples
                --------
                >>> transform([1, 2, 3], scale=2.0)
                [2.0, 4.0, 6.0]

                >>> transform([10, 20], scale=0.5)
                [5.0, 10.0]
                """
                return [x * scale for x in data]
        ''',
        "README.md": """\
            # gdtest-v2-numpy-rich

            A synthetic test package with rich NumPy-style docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-numpy-rich",
        "detected_module": "gdtest_numpy_rich",
        "detected_parser": "numpy",
        "export_names": ["analyze", "transform"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
