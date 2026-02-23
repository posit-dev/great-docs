"""
gdtest_rst_mixed_dirs — Tests multiple RST directives in the same docstrings.

Dimensions: L9
Focus: Multiple different RST directives within a single docstring, rendered as
styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_mixed_dirs",
    "description": "Tests multiple RST directives in same docstrings",
    "dimensions": ["L9"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-mixed-dirs",
            "version": "0.1.0",
            "description": "Test mixed RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_mixed_dirs/__init__.py": '''\
            """Package testing mixed RST directives in docstrings."""

            __version__ = "0.1.0"
            __all__ = ["process_v2", "transform_legacy", "safe_delete"]


            def process_v2(data: list) -> list:
                """
                Process data using the v2 pipeline.

                Parameters
                ----------
                data
                    The data to process.

                Returns
                -------
                list
                    The processed data.

                .. versionadded:: 2.0

                .. note::
                    Replaces the old process() function.

                .. tip::
                    Use with batch_mode for best results.
                """
                return data


            def transform_legacy(data: dict) -> dict:
                """
                Transform data using the legacy algorithm.

                Parameters
                ----------
                data
                    The data dictionary to transform.

                Returns
                -------
                dict
                    The transformed data.

                .. deprecated:: 1.0
                    Use transform_v2() instead.

                .. warning::
                    May produce unexpected results with nested dicts.
                """
                return data


            def safe_delete(item_id: str) -> bool:
                """
                Safely delete an item by its identifier.

                Parameters
                ----------
                item_id
                    The identifier of the item to delete.

                Returns
                -------
                bool
                    True if the item was deleted successfully.

                .. important::
                    Validates before deletion.

                .. caution::
                    Rate limited to 100 calls per minute.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-v2-rst-mixed-dirs

            Tests mixed RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-mixed-dirs",
        "detected_module": "gdtest_rst_mixed_dirs",
        "detected_parser": "numpy",
        "export_names": ["process_v2", "safe_delete", "transform_legacy"],
        "num_exports": 3,
    },
}
