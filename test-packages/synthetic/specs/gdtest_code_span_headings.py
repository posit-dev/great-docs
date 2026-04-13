"""
gdtest_code_span_headings — custom docstring headings containing code spans.

Dimensions: A1, D1, L26
Focus: Tests that custom docstring section headings containing backtick-
       delimited code spans are handled correctly:

       1. Title-casing preserves code spans verbatim (``value=`` stays
          lowercase inside backticks).
       2. Slug / CSS class generation strips backticks and special characters
          (``=``, ``?``) so the resulting ``{.doc-...}`` class is valid.
"""

SPEC = {
    "name": "gdtest_code_span_headings",
    "description": (
        "Custom docstring headings with backtick code spans. "
        "Tests that title-casing preserves code verbatim and slugs are sanitized."
    ),
    "dimensions": ["A1", "D1", "L26"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-code-span-headings",
            "version": "0.1.0",
            "description": "Test code spans in docstring section headings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_code_span_headings/__init__.py": '''\
            """Package with custom docstring section headings containing code spans."""

            __version__ = "0.1.0"
            __all__ = ["compare_values", "filter_range"]


            def compare_values(data, column: str, value=None):
                """Compare column values against a threshold.

                Parameters
                ----------
                data
                    The input data.
                column
                    Column name to compare.
                value
                    Comparison threshold. Accepts scalars, column references,
                    or expressions.

                What Can Be Used in `value=`?
                -----------------------------
                The ``value=`` parameter accepts several types:

                - A scalar like ``10`` or ``"hello"``.
                - A column reference using ``col("other_col")``.
                - An expression using ``expr()``.

                Returns
                -------
                list
                    Filtered results.
                """
                return []


            def filter_range(data, column: str, left=None, right=None):
                """Filter values within a range.

                Parameters
                ----------
                data
                    The input data.
                column
                    Column name to filter.
                left
                    Lower bound of the range.
                right
                    Upper bound of the range.

                What Can Be Used in `left=` and `right=`?
                ------------------------------------------
                The ``left=`` and ``right=`` parameters accept:

                - Scalars (``int``, ``float``, ``str``).
                - Column references.
                - Expressions.

                Returns
                -------
                list
                    Filtered results.
                """
                return []
        ''',
        "README.md": """\
            # gdtest-code-span-headings

            A synthetic test package for code spans in docstring section headings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-code-span-headings",
        "detected_module": "gdtest_code_span_headings",
        "detected_parser": "numpy",
        "export_names": ["compare_values", "filter_range"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        # Headings in the rendered HTML should preserve code spans
        "code_span_headings": {
            "compare_values": {
                # The heading text should contain `value=` as inline code
                "heading_text": "What Can Be Used In `value=`?",
                # The slug/class should be clean (no backticks, =, or ?)
                "expected_class": "doc-what-can-be-used-in-value",
            },
            "filter_range": {
                "heading_text": "What Can Be Used In `left=` And `right=`?",
                "expected_class": "doc-what-can-be-used-in-left-and-right",
            },
        },
    },
}
