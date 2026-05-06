"""
gdtest_deep_nesting — Deeply nested subpackages.

Dimensions: A1, B6, C1, D1, E6, F6, G1, H7
Focus: Package with deeply nested subpackages (level1.level2.level3)
       to test deep module traversal.
"""

SPEC = {
    "name": "gdtest_deep_nesting",
    "description": "Deeply nested subpackages (3 levels)",
    "dimensions": ["A1", "B6", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-deep-nesting",
            "version": "0.1.0",
            "description": "Test deep subpackage traversal",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_deep_nesting/__init__.py": '''\
            """Package with deeply nested subpackages."""

            __version__ = "0.1.0"

            from gdtest_deep_nesting.level1.level2.level3 import deep_func, DeepClass

            __all__ = ["deep_func", "DeepClass"]
        ''',
        "gdtest_deep_nesting/level1/__init__.py": '''\
            """Level 1 subpackage."""
        ''',
        "gdtest_deep_nesting/level1/level2/__init__.py": '''\
            """Level 2 subpackage."""
        ''',
        "gdtest_deep_nesting/level1/level2/level3/__init__.py": '''\
            """Level 3 (deepest) subpackage."""

            __all__ = ["deep_func", "DeepClass"]


            class DeepClass:
                """
                A class defined deep in the package hierarchy.

                Parameters
                ----------
                value
                    Initial value.
                """

                def __init__(self, value: int):
                    self.value = value

                def compute(self) -> int:
                    """
                    Perform computation.

                    Returns
                    -------
                    int
                        Computed result.
                    """
                    return self.value * 2


            def deep_func(x: int) -> int:
                """
                A function at the deepest nesting level.

                Parameters
                ----------
                x
                    Input value.

                Returns
                -------
                int
                    Processed value.
                """
                return x + 1
        ''',
        "README.md": """\
            # gdtest-deep-nesting

            Tests deeply nested subpackage traversal.
        """,
    },
    "expected": {
        "detected_name": "gdtest-deep-nesting",
        "detected_module": "gdtest_deep_nesting",
        "detected_parser": "numpy",
        "export_names": ["deep_func", "DeepClass"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
