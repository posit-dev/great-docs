"""
gdtest_sec_index_opt — Sections with and without auto-generated index pages.

Dimensions: N8
Focus: Two custom sections side by side — one with ``index: true`` (card-based
       index page) and one without (default, navbar links to first page).
"""

SPEC = {
    "name": "gdtest_sec_index_opt",
    "description": "Sections with and without auto-generated index pages.",
    "dimensions": ["N8"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-index-opt",
            "version": "0.1.0",
            "description": "Test section index opt-in behavior.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Examples", "dir": "examples", "index": True},
            {"title": "Tutorials", "dir": "tutorials"},
        ],
    },
    "files": {
        "gdtest_sec_index_opt/__init__.py": (
            '"""Test package for section index opt-in."""\n\n'
            "from .core import analyze, transform\n\n"
            '__all__ = ["analyze", "transform"]\n'
        ),
        "gdtest_sec_index_opt/core.py": '''
            """Core analyze/transform functions."""


            def analyze(data: list) -> dict:
                """Analyze the given data and return summary statistics.

                Parameters
                ----------
                data : list
                    A list of numeric values to analyze.

                Returns
                -------
                dict
                    A dictionary with summary statistics.

                Examples
                --------
                >>> analyze([1, 2, 3])
                {'mean': 2.0, 'count': 3}
                """
                return {"mean": sum(data) / len(data), "count": len(data)}


            def transform(value: str, upper: bool = False) -> str:
                """Transform a string value.

                Parameters
                ----------
                value : str
                    The string to transform.
                upper : bool
                    Whether to convert to upper case.

                Returns
                -------
                str
                    The transformed string.

                Examples
                --------
                >>> transform("hello", upper=True)
                'HELLO'
                """
                return value.upper() if upper else value.lower()
        ''',
        # -- Examples section (will get an auto-generated card index) --
        "examples/basic-usage.qmd": (
            "---\n"
            "title: Basic Usage\n"
            "description: Learn the fundamentals of the package.\n"
            "---\n"
            "\n"
            "# Basic Usage\n"
            "\n"
            "This example covers the basic usage of the package.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_opt import analyze\n"
            "result = analyze([10, 20, 30])\n"
            "print(result)\n"
            "```\n"
        ),
        "examples/advanced-patterns.qmd": (
            "---\n"
            "title: Advanced Patterns\n"
            "description: Explore advanced usage patterns and techniques.\n"
            "---\n"
            "\n"
            "# Advanced Patterns\n"
            "\n"
            "This example covers advanced patterns.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_opt import transform\n"
            "result = transform('hello world', upper=True)\n"
            "```\n"
        ),
        "examples/real-world.qmd": (
            "---\n"
            "title: Real-World Scenario\n"
            "description: A complete real-world example with data analysis.\n"
            "---\n"
            "\n"
            "# Real-World Scenario\n"
            "\n"
            "Putting it all together in a real-world scenario.\n"
        ),
        # -- Tutorials section (no index — navbar links to first page) --
        "tutorials/getting-started.qmd": (
            "---\n"
            "title: Getting Started\n"
            "description: Your first steps with the package.\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "Welcome! This tutorial walks you through your first steps.\n"
        ),
        "tutorials/data-processing.qmd": (
            "---\n"
            "title: Data Processing\n"
            "description: Learn how to process data efficiently.\n"
            "---\n"
            "\n"
            "# Data Processing\n"
            "\n"
            "In this tutorial you will learn to process data.\n"
        ),
        "tutorials/best-practices.qmd": (
            "---\n"
            "title: Best Practices\n"
            "description: Tips and best practices for production use.\n"
            "---\n"
            "\n"
            "# Best Practices\n"
            "\n"
            "Follow these best practices for production deployments.\n"
        ),
        "README.md": (
            "# gdtest-sec-index-opt\n\nTest package demonstrating section index opt-in behavior.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-sec-index-opt",
        "detected_module": "gdtest_sec_index_opt",
        "detected_parser": "numpy",
        "export_names": ["analyze", "transform"],
        "num_exports": 2,
    },
}
