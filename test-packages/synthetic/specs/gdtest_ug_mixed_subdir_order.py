"""
gdtest_ug_mixed_subdir_order — Mixed root files and subdirectories with numeric prefixes.

Dimensions: A1, D1, F3
Focus: User guide that mixes root-level .qmd files with numeric-prefixed
       subdirectories. Tests that the sidebar interleaves files and sections in
       numeric prefix order (01-overview, 02-setup/, 03-usage, 04-advanced/)
       rather than grouping all root files before all sections.
"""

SPEC = {
    "name": "gdtest_ug_mixed_subdir_order",
    "description": (
        "User guide with numeric-prefixed root files interleaved with "
        "numeric-prefixed subdirectory sections. Verifies correct sidebar "
        "ordering when files and folders are mixed."
    ),
    "dimensions": ["A1", "D1", "F3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ug-mixed-subdir-order",
            "version": "0.1.0",
            "description": "Test package for mixed root-file / subdir user guide ordering.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_mixed_subdir_order/__init__.py": '''\
            """Package with mixed root-file and subdirectory user guide."""

            from .core import process, validate

            __version__ = "0.1.0"
            __all__ = ["process", "validate"]
        ''',
        "gdtest_ug_mixed_subdir_order/core.py": '''\
            """Core processing functions."""

            from __future__ import annotations


            def process(data: list[str], *, strict: bool = False) -> list[str]:
                """
                Process a list of items.

                Parameters
                ----------
                data : list[str]
                    Items to process.
                strict : bool
                    Raise on invalid items when True.

                Returns
                -------
                list[str]
                    Processed items.
                """
                return [item.strip() for item in data]


            def validate(value: str) -> bool:
                """
                Validate a single value.

                Parameters
                ----------
                value : str
                    The value to validate.

                Returns
                -------
                bool
                    True if the value is valid.
                """
                return bool(value and value.strip())
        ''',
        # root file #1 — should appear first in sidebar
        "docs/user_guide/01-overview.qmd": """\
            ---
            title: Overview
            ---

            # Overview

            This package provides simple data processing utilities.
        """,
        # subdir #2 — should appear second in sidebar
        "docs/user_guide/02-setup/index.qmd": """\
            ---
            title: Setup
            ---

            Everything you need to install and configure the package.
        """,
        "docs/user_guide/02-setup/01-install.qmd": """\
            ---
            title: Installation
            ---

            ## Installing

            ```bash
            pip install gdtest-ug-mixed-subdir-order
            ```
        """,
        # root file #3 — should appear third in sidebar (after the 02 section)
        "docs/user_guide/03-usage.qmd": """\
            ---
            title: Usage
            ---

            # Usage

            Import and call `process()` with a list of strings.

            ```python
            from gdtest_ug_mixed_subdir_order import process

            result = process(["hello", " world "])
            ```
        """,
        # subdir #4 — should appear fourth in sidebar
        "docs/user_guide/04-advanced/index.qmd": """\
            ---
            title: Advanced Topics
            ---

            Advanced configuration and extension patterns.
        """,
        "docs/user_guide/04-advanced/01-tips.qmd": """\
            ---
            title: Tips
            ---

            ## Performance Tips

            Pass `strict=True` to `process()` to catch malformed inputs early.
        """,
        "README.md": """\
            # gdtest-ug-mixed-subdir-order

            Test package for mixed root-file and subdirectory user guide ordering.
        """,
    },
    "expected": {
        "detected_name": "gdtest-ug-mixed-subdir-order",
        "detected_module": "gdtest_ug_mixed_subdir_order",
        "detected_parser": "numpy",
        "export_names": ["process", "validate"],
        "num_exports": 2,
        # Only root-level files; subdir pages are verified by the dedicated test
        "user_guide_files": ["01-overview.qmd", "03-usage.qmd"],
        # Levels this package cannot achieve
        "coverage_exclude": ["nodoc", "bigcl", "supp", "sechdg", "sbsec"],
    },
}
