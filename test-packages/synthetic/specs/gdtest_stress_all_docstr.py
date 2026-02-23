"""
gdtest_stress_all_docstr — Module with EVERY docstring feature.

Dimensions: L1, L3, L4, L10, L11, L15, L18, L19, L22
Focus: Stress test with every docstring section and feature in a single module:
       Parameters, Returns, Raises, Notes (multi-paragraph with inline code),
       Examples (multiple code blocks), See Also, Warnings, References,
       versionadded, note directive, and Sphinx cross-reference roles.
"""

SPEC = {
    "name": "gdtest_stress_all_docstr",
    "description": "Module with EVERY docstring feature.",
    "dimensions": ["L1", "L3", "L4", "L10", "L11", "L15", "L18", "L19", "L22"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-stress-all-docstr",
            "version": "0.1.0",
            "description": "Stress test with every docstring feature.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_stress_all_docstr/__init__.py": '''\
            """Package stress-testing every docstring feature."""

            __all__ = ["mega_function", "other_func", "DataHolder"]


            def mega_function(data: list, mode: str = "default", threshold: float = 0.5) -> dict:
                r"""Perform a mega computation combining all docstring features.

                Applies a configurable analysis pipeline to the input data,
                returning detailed results. Uses :py:func:`other_func` for
                element-wise transformations and :py:class:`DataHolder` for
                result storage.

                .. versionadded:: 3.0

                .. note:: This replaces the old API.

                Parameters
                ----------
                data : list
                    A list of numeric values to process. Must contain at
                    least one element.
                mode : str, optional
                    The processing mode. One of ``"default"`` or ``"strict"``.
                    Defaults to ``"default"``.
                threshold : float, optional
                    The minimum threshold for filtering values. Values below
                    this threshold are excluded. Defaults to ``0.5``.

                Returns
                -------
                dict
                    A dictionary with the following keys:

                    - ``"result"`` — the computed aggregate value (float).
                    - ``"filtered"`` — data points above threshold (list).
                    - ``"mode"`` — the mode that was used (str).
                    - ``"count"`` — number of points processed (int).

                Raises
                ------
                ValueError
                    If ``data`` is empty or ``mode`` is not recognized.

                Notes
                -----
                The ``"default"`` mode applies a simple mean calculation:

                .. math::

                    R = \\frac{1}{n} \\sum_{i=1}^{n} f(x_i)

                where :math:`f` is the :py:func:`other_func` transformation.

                The ``"strict"`` mode additionally filters values below the
                ``threshold`` before computing the mean. This can significantly
                reduce the number of data points in the output.

                The time complexity is ``O(n)`` for both modes. Memory usage
                is proportional to the size of the input data.

                Warnings
                --------
                Input is modified in-place when ``mode="strict"`` is used.
                Make a copy of the data before calling if you need to preserve
                the original values.

                See Also
                --------
                other_func : Element-wise transformation used internally.
                DataHolder : Class for storing computation results.

                References
                ----------
                .. [1] Smith et al. (2020). "Advanced Data Processing
                   Techniques." Journal of Computation, 15(3), 42-58.

                Examples
                --------
                Basic usage with default mode:

                >>> result = mega_function([1.0, 2.0, 3.0])
                >>> result["mode"]
                'default'
                >>> result["count"]
                3

                Using strict mode with a threshold:

                >>> result = mega_function([0.1, 0.6, 0.9], mode="strict", threshold=0.5)
                >>> result["filtered"]
                [0.6, 0.9]

                The transformation uses :py:func:`other_func` internally:

                >>> result = mega_function([4.0])
                >>> result["result"]
                2.0
                """
                if not data:
                    raise ValueError("data must not be empty")
                if mode not in ("default", "strict"):
                    raise ValueError(f"Unknown mode: {mode}")

                if mode == "strict":
                    filtered = [x for x in data if x >= threshold]
                else:
                    filtered = list(data)

                transformed = [other_func(x) for x in filtered]
                result_value = sum(transformed) / len(transformed) if transformed else 0.0

                return {
                    "result": result_value,
                    "filtered": filtered,
                    "mode": mode,
                    "count": len(filtered),
                }


            def other_func(x: float) -> float:
                """Apply a square-root transformation to a single value.

                Parameters
                ----------
                x : float
                    A numeric value to transform.

                Returns
                -------
                float
                    The square root of the absolute value of ``x``.

                See Also
                --------
                mega_function : Main function that uses this transformation.

                Examples
                --------
                >>> other_func(4.0)
                2.0

                >>> other_func(0.0)
                0.0
                """
                import math
                return math.sqrt(abs(x))


            class DataHolder:
                """A container for holding computation results.

                Parameters
                ----------
                name : str
                    The name of the data holder.

                Examples
                --------
                >>> dh = DataHolder("results")
                >>> dh.get_data()
                {}
                """

                def __init__(self, name: str):
                    """Initialize the DataHolder.

                    Parameters
                    ----------
                    name : str
                        The name of the data holder.
                    """
                    self.name = name
                    self._data: dict = {}

                def get_data(self) -> dict:
                    """Return the stored data.

                    Returns
                    -------
                    dict
                        The stored data dictionary.

                    Examples
                    --------
                    >>> dh = DataHolder("test")
                    >>> dh.get_data()
                    {}
                    """
                    return self._data
        ''',
        "README.md": (
            "# gdtest-v2-stress-all-docstr\n\nStress test with every docstring feature.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-stress-all-docstr",
        "detected_module": "gdtest_stress_all_docstr",
        "detected_parser": "numpy",
        "export_names": ["DataHolder", "mega_function", "other_func"],
        "num_exports": 3,
    },
}
