"""
gdtest_ref_module_expand — Reference config referencing a submodule name.

Dimensions: P6
Focus: Reference config that references a submodule by its full dotted path.
"""

SPEC = {
    "name": "gdtest_ref_module_expand",
    "description": "Reference config referencing a submodule name for expansion.",
    "dimensions": ["P6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-module-expand",
            "version": "0.1.0",
            "description": "Test reference config with submodule expansion.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Utils API",
                "desc": "Utility functions",
                "contents": [
                    {"name": "gdtest_ref_module_expand.utils"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_module_expand/__init__.py": '''\
            """Package with a submodule for reference expansion."""

            __all__ = ["main_func"]


            def main_func(data: str) -> str:
                """Process the main data input.

                Parameters
                ----------
                data : str
                    The data string to process.

                Returns
                -------
                str
                    The processed data.

                Examples
                --------
                >>> main_func("hello")
                'HELLO'
                """
                return data.upper()
        ''',
        "gdtest_ref_module_expand/utils.py": '''\
            """Utility functions for the package."""

            __all__ = ["util_a", "util_b", "util_c"]


            def util_a(value: int) -> int:
                """Double the input value.

                Parameters
                ----------
                value : int
                    The value to double.

                Returns
                -------
                int
                    The doubled value.

                Examples
                --------
                >>> util_a(5)
                10
                """
                return value * 2


            def util_b(text: str) -> str:
                """Reverse the input text.

                Parameters
                ----------
                text : str
                    The text to reverse.

                Returns
                -------
                str
                    The reversed text.

                Examples
                --------
                >>> util_b("abc")
                'cba'
                """
                return text[::-1]


            def util_c(items: list) -> int:
                """Count the number of items in a list.

                Parameters
                ----------
                items : list
                    The list of items to count.

                Returns
                -------
                int
                    The number of items.

                Examples
                --------
                >>> util_c([1, 2, 3])
                3
                """
                return len(items)
        ''',
        "README.md": (
            "# gdtest-v2-ref-module-expand\n\nTest reference config with submodule expansion.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-module-expand",
        "detected_module": "gdtest_ref_module_expand",
        "detected_parser": "numpy",
        "export_names": ["main_func", "util_a", "util_b", "util_c"],
        "num_exports": 4,
    },
}
