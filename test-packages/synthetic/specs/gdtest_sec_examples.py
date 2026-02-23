"""
gdtest_sec_examples — Custom "Examples" section via config.

Dimensions: N1
Focus: Custom section with title "Examples" sourced from examples/ directory.
"""

SPEC = {
    "name": "gdtest_sec_examples",
    "description": "Custom 'Examples' section via sections config.",
    "dimensions": ["N1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-examples",
            "version": "0.1.0",
            "description": "Test custom Examples section.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Examples", "dir": "examples"},
        ],
    },
    "files": {
        "gdtest_sec_examples/__init__.py": '"""Test package for custom Examples section."""\n',
        "gdtest_sec_examples/core.py": '''
            """Core demo/showcase functions."""


            def demo(x: int) -> int:
                """Run a demo with the given input.

                Parameters
                ----------
                x : int
                    The input value for the demo.

                Returns
                -------
                int
                    The demo result.

                Examples
                --------
                >>> demo(5)
                10
                """
                return x * 2


            def showcase(items: list) -> str:
                """Showcase a list of items as a formatted string.

                Parameters
                ----------
                items : list
                    The items to showcase.

                Returns
                -------
                str
                    A formatted string of all items.

                Examples
                --------
                >>> showcase(["a", "b", "c"])
                'a, b, c'
                """
                return ", ".join(str(i) for i in items)
        ''',
        "examples/basic-example.qmd": (
            "---\n"
            "title: Basic Example\n"
            "---\n"
            "\n"
            "# Basic Example\n"
            "\n"
            "A simple example showing how to get started.\n"
        ),
        "examples/advanced-example.qmd": (
            "---\n"
            "title: Advanced Example\n"
            "---\n"
            "\n"
            "# Advanced Example\n"
            "\n"
            "An advanced example demonstrating complex usage patterns.\n"
        ),
        "examples/edge-cases.qmd": (
            "---\n"
            "title: Edge Cases\n"
            "---\n"
            "\n"
            "# Edge Cases\n"
            "\n"
            "Examples covering edge cases and boundary conditions.\n"
        ),
        "README.md": ("# gdtest-v2-sec-examples\n\nTest custom Examples section.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-examples",
        "detected_module": "gdtest_sec_examples",
        "detected_parser": "numpy",
        "export_names": ["demo", "showcase"],
        "num_exports": 2,
    },
}
