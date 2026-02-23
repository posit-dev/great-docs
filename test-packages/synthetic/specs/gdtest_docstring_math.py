"""
gdtest_docstring_math — Math notation in NumPy-style docstrings.

Dimensions: L23
Focus: Two functions with mathematical formulas in their Notes sections,
       using both inline and display math notation.
"""

SPEC = {
    "name": "gdtest_docstring_math",
    "description": "Math notation in docstring Notes sections",
    "dimensions": ["L23"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-math",
            "version": "0.1.0",
            "description": "Test math notation rendering in docstrings",
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
        "gdtest_docstring_math/__init__.py": '''\
            """Package with math notation in docstrings."""

            __version__ = "0.1.0"
            __all__ = ["norm", "softmax"]


            def norm(vector: list) -> float:
                r"""
                Compute the L2 (Euclidean) norm of a vector.

                Returns the magnitude of the input vector, computed as
                the square root of the sum of squared elements.

                Parameters
                ----------
                vector
                    A list of numeric values representing a vector.

                Returns
                -------
                float
                    The L2 norm of the vector.

                Notes
                -----
                Computes the L2 norm:

                .. math::

                    \\|x\\| = \\sqrt{\\sum_{i=1}^{n} x_i^2}

                For a zero vector, the norm is 0.0. The computation uses
                floating-point arithmetic, so results may have small
                rounding errors for very large or very small values.

                Examples
                --------
                >>> norm([3.0, 4.0])
                5.0

                >>> norm([1.0, 0.0, 0.0])
                1.0
                """
                import math

                return math.sqrt(sum(x ** 2 for x in vector))


            def softmax(logits: list) -> list:
                r"""
                Apply the softmax function to a list of logits.

                Converts a vector of raw scores (logits) into a probability
                distribution where each element is in (0, 1) and all
                elements sum to 1.

                Parameters
                ----------
                logits
                    A list of numeric values (raw scores).

                Returns
                -------
                list
                    A list of probabilities summing to 1.0.

                Notes
                -----
                Applies the softmax function:

                .. math::

                    \\sigma(z)_i = \\frac{e^{z_i}}{\\sum_{j=1}^{K} e^{z_j}}

                For numerical stability, the implementation subtracts the
                maximum logit value before exponentiation:

                .. math::

                    \\sigma(z)_i = \\frac{e^{z_i - \\max(z)}}{\\sum_{j=1}^{K} e^{z_j - \\max(z)}}

                This prevents overflow when logit values are large.

                Examples
                --------
                >>> result = softmax([1.0, 2.0, 3.0])
                >>> round(sum(result), 5)
                1.0

                >>> softmax([0.0, 0.0])
                [0.5, 0.5]
                """
                import math

                max_logit = max(logits)
                exps = [math.exp(x - max_logit) for x in logits]
                total = sum(exps)
                return [e / total for e in exps]
        ''',
        "README.md": """\
            # gdtest-v2-docstring-math

            A synthetic test package with math notation in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-math",
        "detected_module": "gdtest_docstring_math",
        "detected_parser": "numpy",
        "export_names": ["norm", "softmax"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
