"""
gdtest_generators — Generator functions (yield).

Dimensions: A1, B1, C14, D1, E6, F6, G1, H7
Focus: Functions using yield to return iterators/generators. Tests
       that generator return types render correctly.
"""

SPEC = {
    "name": "gdtest_generators",
    "description": "Generator functions using yield",
    "dimensions": ["A1", "B1", "C14", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-generators",
            "version": "0.1.0",
            "description": "Test generator function documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_generators/__init__.py": '''\
            """Package with generator functions."""

            from typing import Iterator

            __version__ = "0.1.0"
            __all__ = ["count_up", "fibonacci", "iter_chunks"]


            def count_up(start: int = 0) -> Iterator[int]:
                """
                Count upward from a start value.

                Parameters
                ----------
                start
                    Starting value.

                Returns
                -------
                Iterator[int]
                    An iterator yielding successive integers.
                """
                n = start
                while True:
                    yield n
                    n += 1


            def fibonacci(limit: int = 100) -> Iterator[int]:
                """
                Generate Fibonacci numbers up to a limit.

                Parameters
                ----------
                limit
                    Maximum value to generate.

                Returns
                -------
                Iterator[int]
                    An iterator yielding Fibonacci numbers.
                """
                a, b = 0, 1
                while a <= limit:
                    yield a
                    a, b = b, a + b


            def iter_chunks(data: list, size: int = 10) -> Iterator[list]:
                """
                Iterate over data in chunks.

                Parameters
                ----------
                data
                    Input data list.
                size
                    Chunk size.

                Returns
                -------
                Iterator[list]
                    An iterator yielding list chunks.
                """
                for i in range(0, len(data), size):
                    yield data[i:i + size]
        ''',
        "README.md": """\
            # gdtest-generators

            Tests documentation of generator functions using yield.
        """,
    },
    "expected": {
        "detected_name": "gdtest-generators",
        "detected_module": "gdtest_generators",
        "detected_parser": "numpy",
        "export_names": ["count_up", "fibonacci", "iter_chunks"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
