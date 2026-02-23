"""
gdtest_sec_multi — Multiple custom sections: Examples + Tutorials + Recipes.

Dimensions: N6
Focus: Three custom sections defined simultaneously via sections config.
"""

SPEC = {
    "name": "gdtest_sec_multi",
    "description": "Multiple custom sections: Examples, Tutorials, and Recipes.",
    "dimensions": ["N6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-multi",
            "version": "0.1.0",
            "description": "Test multiple custom sections.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Examples", "dir": "examples"},
            {"title": "Tutorials", "dir": "tutorials"},
            {"title": "Recipes", "dir": "recipes"},
        ],
    },
    "files": {
        "gdtest_sec_multi/__init__.py": '"""Test package for multiple custom sections."""\n',
        "gdtest_sec_multi/core.py": '''
            """Core multi_demo/combine functions."""


            def multi_demo(x: int) -> int:
                """Run a multi-section demo with the given input.

                Parameters
                ----------
                x : int
                    The input value for the demo.

                Returns
                -------
                int
                    The demo result doubled.

                Examples
                --------
                >>> multi_demo(5)
                10
                """
                return x * 2


            def combine(a: str, b: str) -> str:
                """Combine two strings with a separator.

                Parameters
                ----------
                a : str
                    The first string.
                b : str
                    The second string.

                Returns
                -------
                str
                    The combined string.

                Examples
                --------
                >>> combine("hello", "world")
                'hello-world'
                """
                return f"{a}-{b}"
        ''',
        "examples/demo.qmd": (
            "---\n"
            "title: Demo Example\n"
            "---\n"
            "\n"
            "# Demo Example\n"
            "\n"
            "A demonstration example for the multi-section package.\n"
        ),
        "tutorials/basics.qmd": (
            "---\n"
            "title: Basics Tutorial\n"
            "---\n"
            "\n"
            "# Basics Tutorial\n"
            "\n"
            "A tutorial covering the basic concepts.\n"
        ),
        "recipes/quick.qmd": (
            "---\ntitle: Quick Recipe\n---\n\n# Quick Recipe\n\nA quick recipe for common tasks.\n"
        ),
        "README.md": ("# gdtest-v2-sec-multi\n\nTest multiple custom sections.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-multi",
        "detected_module": "gdtest_sec_multi",
        "detected_parser": "numpy",
        "export_names": ["combine", "multi_demo"],
        "num_exports": 2,
    },
}
