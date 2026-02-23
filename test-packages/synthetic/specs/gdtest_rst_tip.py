"""
gdtest_rst_tip — Tests .. tip:: directives in docstrings.

Dimensions: L5
Focus: RST tip directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_tip",
    "description": "Tests tip RST directives in docstrings",
    "dimensions": ["L5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-tip",
            "version": "0.1.0",
            "description": "Test tip RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_tip/__init__.py": '''\
            """Package testing tip RST directives."""

            __version__ = "0.1.0"
            __all__ = ["optimize", "batch_process"]


            def optimize(data: list) -> list:
                """
                Optimize the given data for processing.

                Parameters
                ----------
                data
                    The data to optimize.

                Returns
                -------
                list
                    The optimized data.

                .. tip::
                    Pre-sort the data for better performance.
                """
                return data


            def batch_process(items: list, chunk_size: int = 100) -> list:
                """
                Process items in batches.

                Parameters
                ----------
                items
                    The items to process.
                chunk_size
                    The number of items per batch.

                Returns
                -------
                list
                    The processed results.

                .. tip::
                    Use chunk_size=50 for memory-constrained systems.
                """
                return items
        ''',
        "README.md": """\
            # gdtest-v2-rst-tip

            Tests tip RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-tip",
        "detected_module": "gdtest_rst_tip",
        "detected_parser": "numpy",
        "export_names": ["batch_process", "optimize"],
        "num_exports": 2,
    },
}
