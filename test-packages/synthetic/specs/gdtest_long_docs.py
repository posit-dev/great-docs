"""
gdtest_long_docs — Very long docstrings with multiple sections.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Functions with extensive docstrings containing Parameters, Returns,
       Raises, Notes, Examples, Warnings, and References sections.
"""

SPEC = {
    "name": "gdtest_long_docs",
    "description": "Very long docstrings with many sections",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-long-docs",
            "version": "0.1.0",
            "description": "Test long multi-section docstrings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_long_docs/__init__.py": '''\
            """Package with extensively documented functions."""

            __version__ = "0.1.0"
            __all__ = ["complex_transform", "detailed_validate", "full_process"]


            def complex_transform(
                data: list,
                mode: str = "standard",
                threshold: float = 0.5,
                inplace: bool = False,
            ) -> list:
                """
                Apply a complex transformation to input data.

                This function performs a multi-step transformation on the input
                data. The transformation is controlled by the ``mode`` parameter,
                which can be ``"standard"``, ``"fast"``, or ``"precise"``.

                Parameters
                ----------
                data
                    Input data as a list of numeric values. Each element must
                    be a finite number (int or float). Empty lists are allowed
                    and will return empty lists.
                mode
                    Transformation mode. One of:

                    - ``"standard"`` — balanced speed/accuracy (default)
                    - ``"fast"`` — optimized for speed at cost of precision
                    - ``"precise"`` — maximum accuracy, slower
                threshold
                    Minimum value threshold. Values below this are filtered
                    out before transformation. Must be non-negative.
                inplace
                    If True, modify the input list in place. If False (default),
                    return a new list.

                Returns
                -------
                list
                    Transformed data. If ``inplace=True``, this is the same
                    object as ``data``.

                Raises
                ------
                ValueError
                    If ``mode`` is not one of the recognized values.
                TypeError
                    If ``data`` contains non-numeric elements.

                Notes
                -----
                The transformation algorithm is based on the windowed moving
                average technique described in [1]_. For large datasets
                (>10,000 elements), the ``"fast"`` mode is recommended.

                The time complexity is O(n) for ``"fast"`` mode and O(n log n)
                for ``"precise"`` mode.

                Warnings
                --------
                Using ``inplace=True`` modifies the original data and cannot
                be undone. Always make a copy if you need the original data.

                Examples
                --------
                Basic usage with default parameters:

                >>> from gdtest_long_docs import complex_transform
                >>> complex_transform([1, 2, 3, 4, 5])
                [1, 2, 3, 4, 5]

                Using fast mode:

                >>> complex_transform([1, 2, 3], mode="fast")
                [1, 2, 3]

                With threshold filtering:

                >>> complex_transform([0.1, 0.5, 1.0], threshold=0.3)
                [0.5, 1.0]

                References
                ----------
                .. [1] Smith, J. (2020). "Data Transformation Techniques."
                   Journal of Applied Computing, 15(3), 42-58.
                """
                return data


            def detailed_validate(
                schema: dict,
                data: dict,
                strict: bool = True,
            ) -> dict:
                """
                Validate data against a schema with detailed error reporting.

                Performs comprehensive validation of ``data`` against the
                provided ``schema`` dictionary. Each key in the schema maps
                to a type or validator specification.

                Parameters
                ----------
                schema
                    Validation schema. Keys are field names, values are type
                    objects or callable validators. Example::

                        schema = {
                            "name": str,
                            "age": int,
                            "email": lambda x: "@" in x,
                        }
                data
                    Data dictionary to validate.
                strict
                    If True (default), raise on first error. If False,
                    collect all errors and return them.

                Returns
                -------
                dict
                    Validation report with keys:

                    - ``"valid"`` (bool) — overall result
                    - ``"errors"`` (list) — list of error messages
                    - ``"fields_checked"`` (int) — count of fields validated

                Raises
                ------
                ValueError
                    If ``strict=True`` and validation fails.
                KeyError
                    If schema references a field not present in data.

                Notes
                -----
                Schema validators receive the value and should return True
                for valid data or raise an exception/return False for invalid.

                Examples
                --------
                >>> detailed_validate({"name": str}, {"name": "Alice"})
                {'valid': True, 'errors': [], 'fields_checked': 1}
                """
                return {"valid": True, "errors": [], "fields_checked": len(schema)}


            def full_process(
                items: list,
                pipeline: list = None,
                verbose: bool = False,
                max_workers: int = 1,
                timeout: float = 30.0,
            ) -> dict:
                """
                Process items through a configurable pipeline.

                Applies each stage in ``pipeline`` to the items sequentially
                (or in parallel if ``max_workers > 1``).

                Parameters
                ----------
                items
                    List of items to process.
                pipeline
                    List of callable stages. Each receives items and returns
                    modified items. If None, uses a default pipeline.
                verbose
                    If True, print progress information.
                max_workers
                    Number of parallel workers. Use 1 for sequential.
                timeout
                    Maximum processing time in seconds per stage.

                Returns
                -------
                dict
                    Processing results with keys:

                    - ``"items"`` — processed items
                    - ``"stages_run"`` — number of stages executed
                    - ``"elapsed"`` — total time in seconds

                Raises
                ------
                TimeoutError
                    If any stage exceeds the timeout.
                RuntimeError
                    If a pipeline stage fails.

                Notes
                -----
                Parallel processing uses a thread pool. For CPU-bound stages,
                consider using ``max_workers=1`` to avoid GIL contention.

                Examples
                --------
                >>> full_process([1, 2, 3])
                {'items': [1, 2, 3], 'stages_run': 0, 'elapsed': 0.0}

                >>> full_process([1, 2, 3], pipeline=[str], verbose=True)
                Processing stage 1/1...
                {'items': ['1', '2', '3'], 'stages_run': 1, 'elapsed': 0.0}
                """
                return {"items": items, "stages_run": 0, "elapsed": 0.0}
        ''',
        "README.md": """\
            # gdtest-long-docs

            Tests functions with very long, multi-section docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-long-docs",
        "detected_module": "gdtest_long_docs",
        "detected_parser": "numpy",
        "export_names": ["complex_transform", "detailed_validate", "full_process"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
