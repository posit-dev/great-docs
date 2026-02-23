"""
gdtest_docstring_combo — Stress test combining ALL docstring content features.

Dimensions: L9, L14, L15, L18, L19, L22, L23
Focus: One complex function with every docstring section (Parameters, Returns,
       Raises, Notes with math, Examples with code blocks, See Also, References,
       versionadded, Sphinx cross-references) plus a simpler helper function.
"""

SPEC = {
    "name": "gdtest_docstring_combo",
    "description": "Stress test combining all docstring content features in one module",
    "dimensions": ["L9", "L14", "L15", "L18", "L19", "L22", "L23"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-combo",
            "version": "0.1.0",
            "description": "Test all docstring features combined",
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
        "gdtest_docstring_combo/__init__.py": '''\
            """Package stress-testing all docstring content features."""

            __version__ = "0.1.0"
            __all__ = ["advanced_compute", "helper"]


            def advanced_compute(data: list, method: str = "fast") -> dict:
                r"""
                Perform advanced computation on data using the specified method.

                Applies a configurable analysis pipeline to the input data,
                returning detailed results including computed values,
                diagnostics, and metadata. Uses :py:func:`helper` internally
                for element-wise transformations.

                .. versionadded:: 3.0

                Parameters
                ----------
                data
                    A list of numeric values to process. Must contain at
                    least one element.
                method
                    The computation method. One of ``"fast"`` or ``"precise"``.
                    The ``"fast"`` method uses approximate algorithms while
                    ``"precise"`` uses exact arithmetic at the cost of speed.
                    Defaults to ``"fast"``.

                Returns
                -------
                dict
                    A dictionary with the following keys:

                    - ``"result"`` — the computed aggregate value (float).
                    - ``"transformed"`` — element-wise transformed data (list).
                    - ``"method"`` — the method that was used (str).
                    - ``"n"`` — the number of data points processed (int).

                Raises
                ------
                ValueError
                    If ``data`` is empty or ``method`` is not recognized.
                TypeError
                    If ``data`` contains non-numeric values.
                OverflowError
                    If intermediate computations exceed float range.

                Notes
                -----
                The ``"fast"`` method computes an approximate result using
                the following formula:

                .. math::

                    R = \\frac{1}{n} \\sum_{i=1}^{n} h(x_i)

                where :math:`h` is the :py:func:`helper` transformation and
                :math:`n` is the number of data points.

                The ``"precise"`` method uses compensated summation (Kahan
                algorithm) to minimize floating-point rounding errors. This
                is especially important when data values span many orders
                of magnitude.

                The overall time complexity is ``O(n)`` for both methods,
                but the ``"precise"`` method has approximately 4x the
                constant factor due to the compensation arithmetic.

                Warnings
                --------
                The ``"fast"`` method may produce results with relative
                error up to 1e-10 for datasets with high dynamic range.

                See Also
                --------
                helper : Element-wise transformation used internally.

                References
                ----------
                .. [1] Kahan, W. (1965). "Further remarks on reducing
                   truncation errors." Communications of the ACM, 8(1), 40.
                .. [2] Higham, N.J. (2002). "Accuracy and Stability of
                   Numerical Algorithms", 2nd edition, SIAM.

                Examples
                --------
                Basic usage with the default fast method:

                >>> result = advanced_compute([1.0, 2.0, 3.0])
                >>> result["method"]
                'fast'
                >>> result["n"]
                3

                Using the precise method:

                >>> result = advanced_compute([1.0, 2.0], method="precise")
                >>> result["method"]
                'precise'

                The transformed values are computed via :py:func:`helper`:

                >>> result = advanced_compute([4.0])
                >>> result["transformed"]
                [2.0]
                """
                import math

                if not data:
                    raise ValueError("data must not be empty")

                if method not in ("fast", "precise"):
                    raise ValueError(f"Unknown method: {method}")

                transformed = [helper(x) for x in data]

                if method == "fast":
                    result_value = sum(transformed) / len(transformed)
                else:
                    # Kahan compensated summation
                    total = 0.0
                    comp = 0.0
                    for val in transformed:
                        y = val - comp
                        t = total + y
                        comp = (t - total) - y
                        total = t
                    result_value = total / len(transformed)

                return {
                    "result": result_value,
                    "transformed": transformed,
                    "method": method,
                    "n": len(data),
                }


            def helper(x: float) -> float:
                """
                Apply a square-root transformation to a single value.

                Computes the square root of the absolute value of ``x``,
                preserving the original sign.

                Parameters
                ----------
                x
                    A numeric value to transform.

                Returns
                -------
                float
                    The signed square root: ``sign(x) * sqrt(abs(x))``.

                Notes
                -----
                This function is used internally by
                :py:func:`advanced_compute` for element-wise data
                transformation.

                Examples
                --------
                >>> helper(4.0)
                2.0

                >>> helper(-9.0)
                -3.0

                >>> helper(0.0)
                0.0
                """
                import math

                if x >= 0:
                    return math.sqrt(x)
                else:
                    return -math.sqrt(-x)
        ''',
        "README.md": """\
            # gdtest-v2-docstring-combo

            A synthetic test package combining all docstring content features.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-combo",
        "detected_module": "gdtest_docstring_combo",
        "detected_parser": "numpy",
        "export_names": ["advanced_compute", "helper"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
