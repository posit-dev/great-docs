"""
gdtest_jupyter_kernel — Tests jupyter: 'python3' explicit config.

Dimensions: K17
Focus: jupyter config option set to an explicit kernel name.
"""

SPEC = {
    "name": "gdtest_jupyter_kernel",
    "description": "Tests jupyter: python3 config",
    "dimensions": ["K17"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-jupyter-kernel",
            "version": "0.1.0",
            "description": "Test jupyter python3 config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "jupyter": "python3",
    },
    "files": {
        "gdtest_jupyter_kernel/__init__.py": '''\
            """Package testing jupyter python3 config."""

            __version__ = "0.1.0"
            __all__ = ["compute", "evaluate"]


            def compute(x: float, y: float) -> float:
                """
                Compute the sum of two numbers.

                Parameters
                ----------
                x
                    The first number.
                y
                    The second number.

                Returns
                -------
                float
                    The sum of x and y.
                """
                return x + y


            def evaluate(expr: str) -> float:
                """
                Evaluate a mathematical expression string.

                Parameters
                ----------
                expr
                    The expression to evaluate.

                Returns
                -------
                float
                    The result of the evaluation.
                """
                return 0.0
        ''',
        "README.md": """\
            # gdtest-v2-jupyter-kernel

            Tests jupyter: python3 config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-jupyter-kernel",
        "detected_module": "gdtest_jupyter_kernel",
        "detected_parser": "numpy",
        "export_names": ["compute", "evaluate"],
        "num_exports": 2,
    },
}
