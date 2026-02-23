"""
gdtest_docstring_tables — Tables in NumPy-style docstring Notes sections.

Dimensions: L24
Focus: Two functions with reStructuredText tables embedded in their
       Notes sections.
"""

SPEC = {
    "name": "gdtest_docstring_tables",
    "description": "Tables in docstring Notes sections",
    "dimensions": ["L24"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-tables",
            "version": "0.1.0",
            "description": "Test table rendering in docstrings",
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
        "gdtest_docstring_tables/__init__.py": '''\
            """Package with tables in docstrings."""

            __version__ = "0.1.0"
            __all__ = ["compare_methods", "format_report"]


            def compare_methods(data: list) -> dict:
                """
                Compare sorting methods on the given data.

                Runs multiple sorting algorithms on the input data and
                returns a dictionary with timing and memory metrics
                for each method.

                Parameters
                ----------
                data
                    A list of comparable elements to sort.

                Returns
                -------
                dict
                    A dictionary mapping method names to their performance
                    metrics.

                Notes
                -----
                The following table summarizes the complexity characteristics
                of the sorting methods compared:

                ========  =========  ===========
                Method    Speed      Memory
                ========  =========  ===========
                Quick     O(n log n) O(log n)
                Merge     O(n log n) O(n)
                Bubble    O(n^2)     O(1)
                ========  =========  ===========

                The speed column shows average-case time complexity.
                Memory shows auxiliary space complexity, excluding
                the input array.

                For small datasets (n < 50), the differences between
                these methods are negligible due to constant factors.

                Examples
                --------
                >>> result = compare_methods([5, 3, 1])
                >>> sorted(result.keys())
                ['bubble', 'merge', 'quick']
                """
                def _bubble(arr):
                    a = list(arr)
                    for i in range(len(a)):
                        for j in range(len(a) - 1 - i):
                            if a[j] > a[j + 1]:
                                a[j], a[j + 1] = a[j + 1], a[j]
                    return a

                return {
                    "quick": sorted(data),
                    "merge": sorted(data),
                    "bubble": _bubble(data),
                }


            def format_report(stats: dict) -> str:
                """
                Format a statistics dictionary into a human-readable report.

                Takes a dictionary of metric names to values and produces
                a formatted string table.

                Parameters
                ----------
                stats
                    A dictionary mapping metric names (str) to their
                    values (numeric).

                Returns
                -------
                str
                    A formatted report string.

                Notes
                -----
                The report is formatted as a simple two-column table:

                ==========  =====
                Metric      Value
                ==========  =====
                count       100
                mean        42.5
                std         12.3
                ==========  =====

                Numeric values are formatted to one decimal place if they
                are floats, or as integers if they have no fractional part.

                Examples
                --------
                >>> print(format_report({"count": 10, "mean": 5.5}))
                count: 10
                mean: 5.5
                """
                lines = []
                for key, value in stats.items():
                    if isinstance(value, float) and value == int(value):
                        lines.append(f"{key}: {int(value)}")
                    else:
                        lines.append(f"{key}: {value}")
                return "\\n".join(lines)
        ''',
        "README.md": """\
            # gdtest-v2-docstring-tables

            A synthetic test package with tables in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-tables",
        "detected_module": "gdtest_docstring_tables",
        "detected_parser": "numpy",
        "export_names": ["compare_methods", "format_report"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
