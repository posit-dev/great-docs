"""
gdtest_google_rich — Rich Google-style docstrings with ALL sections.

Dimensions: L16
Focus: Two functions with comprehensive Google docstring sections including
       Args, Returns, Raises, Note, Example, Warning, References, and See Also.
"""

SPEC = {
    "name": "gdtest_google_rich",
    "description": "Rich Google-style docstrings with all sections",
    "dimensions": ["L16"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-google-rich",
            "version": "0.1.0",
            "description": "Test rich Google docstring section rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "google",
    },
    "files": {
        "gdtest_google_rich/__init__.py": '''\
            """Package with rich Google-style docstrings."""

            __version__ = "0.1.0"
            __all__ = ["process", "validate"]


            def process(items: list, strict: bool = False) -> dict:
                """Process a list of items and return a summary.

                Iterates through the items, applies validation and
                aggregation, and returns a summary dictionary with
                counts and status information.

                Args:
                    items: A list of items to process. Each item should
                        be a string or convertible to string.
                    strict: If True, raise on invalid items instead of
                        skipping them. Defaults to False.

                Returns:
                    A dictionary with the following keys:

                    - ``"processed"`` — number of successfully processed items.
                    - ``"skipped"`` — number of skipped items (0 if strict).
                    - ``"status"`` — ``"complete"`` or ``"partial"``.

                Raises:
                    ValueError: If ``items`` is empty.
                    TypeError: If an item is not convertible to string
                        and ``strict`` is True.

                Note:
                    The processing order follows the input list order.
                    Items are processed sequentially and results are
                    deterministic for the same input.

                Example:
                    >>> process(["a", "b", "c"])
                    {'processed': 3, 'skipped': 0, 'status': 'complete'}

                    >>> process(["a", None, "c"], strict=False)
                    {'processed': 2, 'skipped': 1, 'status': 'partial'}

                Warning:
                    Large lists (>10,000 items) may cause significant
                    memory usage. Consider batching for large inputs.

                References:
                    Gang of Four, "Design Patterns", Iterator pattern.

                See Also:
                    ``validate``: Validate a schema before processing.
                """
                if not items:
                    raise ValueError("items must not be empty")

                processed = 0
                skipped = 0
                for item in items:
                    try:
                        str(item)
                        processed += 1
                    except Exception:
                        if strict:
                            raise TypeError(f"Cannot convert {item!r} to string")
                        skipped += 1

                status = "complete" if skipped == 0 else "partial"
                return {"processed": processed, "skipped": skipped, "status": status}


            def validate(schema: dict, data: dict) -> bool:
                """Validate data against a schema dictionary.

                Checks that all keys in the schema are present in data
                and that value types match the schema specification.

                Args:
                    schema: A dictionary mapping key names to expected
                        types (e.g., ``{"name": str, "age": int}``).
                    data: The data dictionary to validate against
                        the schema.

                Returns:
                    True if the data conforms to the schema.

                Raises:
                    KeyError: If a required key from the schema is
                        missing in the data.
                    TypeError: If a value in data does not match the
                        expected type from the schema.

                Note:
                    Only top-level keys are validated. Nested dicts
                    are not recursively checked.
                """
                for key, expected_type in schema.items():
                    if key not in data:
                        raise KeyError(f"Missing key: {key}")
                    if not isinstance(data[key], expected_type):
                        raise TypeError(
                            f"Key '{key}': expected {expected_type.__name__}, "
                            f"got {type(data[key]).__name__}"
                        )
                return True
        ''',
        "README.md": """\
            # gdtest-v2-google-rich

            A synthetic test package with rich Google-style docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-google-rich",
        "detected_module": "gdtest_google_rich",
        "detected_parser": "google",
        "export_names": ["process", "validate"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
