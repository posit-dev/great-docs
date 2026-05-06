"""
gdtest_nodoc — %nodoc directive for excluding items.

Dimensions: A1, B1, C4, D1, E4, F6, G1, H7
Focus: 4 functions, 2 with %nodoc. Tests that %nodoc items are excluded
       from sections despite being in __all__.
"""

SPEC = {
    "name": "gdtest_nodoc",
    "description": "%nodoc directive — items excluded from docs",
    "dimensions": ["A1", "B1", "C4", "D1", "E4", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-nodoc",
            "version": "0.1.0",
            "description": "A synthetic test package testing %nodoc",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_nodoc/__init__.py": '''\
            """Package demonstrating %nodoc directive."""

            __version__ = "0.1.0"
            __all__ = ["Calculator", "compute", "reset", "debug_info"]


            class Calculator:
                """
                A simple calculator.

                Parameters
                ----------
                precision
                    Decimal precision.
                """

                def __init__(self, precision: int = 2):
                    self.precision = precision
                    self._result = 0.0

                def add(self, value: float) -> float:
                    """
                    Add a value.

                    Parameters
                    ----------
                    value
                        Value to add.

                    Returns
                    -------
                    float
                        Current result.
                    """
                    self._result += value
                    return round(self._result, self.precision)


            def compute(expression: str) -> float:
                """
                Evaluate a math expression.

                Parameters
                ----------
                expression
                    A math expression string.

                Returns
                -------
                float
                    The result.
                """
                return 0.0


            def reset() -> None:
                """
                Reset the calculator state.

                %nodoc
                """
                pass


            def debug_info() -> dict:
                """
                Return debug information.

                %nodoc

                Returns
                -------
                dict
                    Debug details.
                """
                return {}
        ''',
        "README.md": """\
            # gdtest-nodoc

            A synthetic test package testing the ``%nodoc`` directive.
        """,
    },
    "expected": {
        "detected_name": "gdtest-nodoc",
        "detected_module": "gdtest_nodoc",
        "detected_parser": "numpy",
        "export_names": ["Calculator", "compute", "reset", "debug_info"],
        "num_exports": 4,
        "nodoc_items": ["reset", "debug_info"],
        "documented_items": ["Calculator", "compute"],
        "has_user_guide": False,
        "coverage_exclude": ['bigcl', 'ug', 'supp', 'sechdg', 'sbsec', 'hdg'],
},
}
