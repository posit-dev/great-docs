"""
gdtest_sec_with_ref — Custom Tutorials section combined with explicit reference config.

Dimensions: N2, P1
Focus: Custom section coexisting with explicit reference configuration.
"""

SPEC = {
    "name": "gdtest_sec_with_ref",
    "description": "Custom Tutorials section combined with explicit reference config.",
    "dimensions": ["N2", "P1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-with-ref",
            "version": "0.1.0",
            "description": "Test custom section with explicit reference config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Tutorials", "dir": "tutorials"},
        ],
        "reference": [
            {
                "title": "Core",
                "desc": "Core API",
                "contents": [
                    {"name": "process"},
                    {"name": "analyze"},
                ],
            },
            {
                "title": "Helpers",
                "desc": "Helper functions",
                "contents": [
                    {"name": "format_output"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_sec_with_ref/__init__.py": '"""Test package for custom section with reference config."""\n',
        "gdtest_sec_with_ref/core.py": '''
            """Core process/analyze/format_output functions."""


            def process(data: list) -> list:
                """Process a list of data items.

                Parameters
                ----------
                data : list
                    The raw data to process.

                Returns
                -------
                list
                    The processed data.

                Examples
                --------
                >>> process([1, 2, 3])
                [2, 4, 6]
                """
                return [x * 2 for x in data]


            def analyze(data: list) -> dict:
                """Analyze a list of data and return statistics.

                Parameters
                ----------
                data : list
                    The data to analyze.

                Returns
                -------
                dict
                    A dictionary with analysis results.

                Examples
                --------
                >>> analyze([10, 20, 30])
                {'mean': 20.0, 'count': 3}
                """
                if not data:
                    return {"mean": 0.0, "count": 0}
                return {"mean": sum(data) / len(data), "count": len(data)}


            def format_output(result: dict) -> str:
                """Format an analysis result as a readable string.

                Parameters
                ----------
                result : dict
                    The result dictionary to format.

                Returns
                -------
                str
                    A formatted string representation of the result.

                Examples
                --------
                >>> format_output({"mean": 2.0, "count": 3})
                'mean=2.0, count=3'
                """
                return ", ".join(f"{k}={v}" for k, v in result.items())
        ''',
        "tutorials/step1.qmd": (
            "---\n"
            "title: Step 1 - Getting Started\n"
            "---\n"
            "\n"
            "# Step 1 - Getting Started\n"
            "\n"
            "The first step in the tutorial series.\n"
        ),
        "tutorials/step2.qmd": (
            "---\n"
            "title: Step 2 - Going Further\n"
            "---\n"
            "\n"
            "# Step 2 - Going Further\n"
            "\n"
            "The second step in the tutorial series.\n"
        ),
        "README.md": (
            "# gdtest-v2-sec-with-ref\n\nTest custom section with explicit reference config.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-with-ref",
        "detected_module": "gdtest_sec_with_ref",
        "detected_parser": "numpy",
        "export_names": ["analyze", "format_output", "process"],
        "num_exports": 3,
    },
}
