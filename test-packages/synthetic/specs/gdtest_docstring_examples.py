"""
gdtest_docstring_examples — Extended Examples sections with multiple code blocks.

Dimensions: L18
Focus: Two functions with multi-block Examples sections containing multiple
       code blocks with expected output and interleaving prose.
"""

SPEC = {
    "name": "gdtest_docstring_examples",
    "description": "Extended Examples sections with multiple code blocks and output",
    "dimensions": ["L18"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-examples",
            "version": "0.1.0",
            "description": "Test extended Examples section rendering",
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
        "gdtest_docstring_examples/__init__.py": '''\
            """Package with extended Examples sections."""

            __version__ = "0.1.0"
            __all__ = ["fibonacci", "factorial"]


            def fibonacci(n: int) -> list:
                """
                Generate the first n Fibonacci numbers.

                Computes the Fibonacci sequence starting from 0 and returns
                a list of the first ``n`` values.

                Parameters
                ----------
                n
                    The number of Fibonacci values to generate. Must be
                    a positive integer.

                Returns
                -------
                list
                    A list of the first ``n`` Fibonacci numbers.

                Raises
                ------
                ValueError
                    If ``n`` is less than 1.

                Examples
                --------
                >>> fibonacci(5)
                [0, 1, 1, 2, 3]
                >>> fibonacci(1)
                [0]

                You can also use it with larger values:

                >>> len(fibonacci(100))
                100

                Edge case with exactly two values:

                >>> fibonacci(2)
                [0, 1]
                """
                if n < 1:
                    raise ValueError("n must be at least 1")

                result = [0]
                a, b = 0, 1
                for _ in range(1, n):
                    result.append(b)
                    a, b = b, a + b
                return result


            def factorial(n: int) -> int:
                """
                Compute the factorial of a non-negative integer.

                Returns the product of all positive integers less than
                or equal to ``n``. By convention, ``factorial(0)`` is 1.

                Parameters
                ----------
                n
                    A non-negative integer whose factorial is to be computed.

                Returns
                -------
                int
                    The factorial of ``n``.

                Raises
                ------
                ValueError
                    If ``n`` is negative.

                Examples
                --------
                >>> factorial(5)
                120
                >>> factorial(0)
                1

                Factorials grow very quickly:

                >>> factorial(10)
                3628800
                >>> factorial(20)
                2432902008176640000

                Works with small values too:

                >>> factorial(1)
                1
                >>> factorial(2)
                2
                """
                if n < 0:
                    raise ValueError("n must be non-negative")

                result = 1
                for i in range(2, n + 1):
                    result *= i
                return result
        ''',
        "README.md": """\
            # gdtest-v2-docstring-examples

            A synthetic test package with extended Examples sections.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-examples",
        "detected_module": "gdtest_docstring_examples",
        "detected_parser": "numpy",
        "export_names": ["factorial", "fibonacci"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
