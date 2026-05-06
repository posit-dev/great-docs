"""
gdtest_math_docs — Docstrings with LaTeX math notation.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Docstrings containing inline and block math notation.
       Tests that math renders (or at least doesn't break the page).
"""

SPEC = {
    "name": "gdtest_math_docs",
    "description": "Docstrings with LaTeX math notation",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-math-docs",
            "version": "0.1.0",
            "description": "Test math in docstrings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_math_docs/__init__.py": '''\
            """Package with math-heavy docstrings."""

            import math

            __version__ = "0.1.0"
            __all__ = ["euclidean_distance", "sigmoid", "softmax"]


            def euclidean_distance(x: list, y: list) -> float:
                """
                Compute Euclidean distance between two vectors.

                The Euclidean distance is defined as:

                .. math::

                    d(x, y) = \\\\sqrt{\\\\sum_{i=1}^{n} (x_i - y_i)^2}

                Parameters
                ----------
                x
                    First vector.
                y
                    Second vector.

                Returns
                -------
                float
                    The Euclidean distance :math:`d(x, y)`.
                """
                return math.sqrt(sum((a - b) ** 2 for a, b in zip(x, y)))


            def sigmoid(x: float) -> float:
                """
                Compute the sigmoid function.

                The sigmoid function is :math:`\\\\sigma(x) = \\\\frac{1}{1 + e^{-x}}`.

                Parameters
                ----------
                x
                    Input value.

                Returns
                -------
                float
                    Sigmoid output in range :math:`(0, 1)`.
                """
                return 1.0 / (1.0 + math.exp(-x))


            def softmax(values: list) -> list:
                """
                Compute softmax probabilities.

                For a vector :math:`z`, the softmax of element :math:`j` is:

                .. math::

                    \\\\text{softmax}(z)_j = \\\\frac{e^{z_j}}{\\\\sum_{k=1}^{K} e^{z_k}}

                Parameters
                ----------
                values
                    Input values.

                Returns
                -------
                list
                    Probability distribution that sums to 1.
                """
                max_val = max(values)
                exps = [math.exp(v - max_val) for v in values]
                total = sum(exps)
                return [e / total for e in exps]
        ''',
        "README.md": """\
            # gdtest-math-docs

            Tests LaTeX math notation in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-math-docs",
        "detected_module": "gdtest_math_docs",
        "detected_parser": "numpy",
        "export_names": ["euclidean_distance", "sigmoid", "softmax"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
