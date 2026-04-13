"""
gdtest_homepage_wide — Homepage with wide content and column-margin sidebar.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Verifies that wide content on the homepage (code blocks, tables)
       renders at full width when the column-margin metadata sidebar is
       present.  The column-margin div triggers Quarto's page-columns
       grid which can narrow the body-content track; the gd-homepage
       body class + CSS fix should prevent the ~100px left indentation.
"""

SPEC = {
    "name": "gdtest_homepage_wide",
    "description": "Homepage with wide content and column-margin sidebar",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-homepage-wide",
            "version": "1.0.0",
            "description": "Tests that wide homepage content is not indented by column-margin sidebar",
            "license": "MIT",
            "authors": [
                {"name": "Test Author", "email": "test@example.com"},
            ],
            "urls": {
                "Homepage": "https://example.com/gdtest-homepage-wide",
                "Repository": "https://github.com/example/gdtest-homepage-wide",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_homepage_wide/__init__.py": '''\
            """A test package for homepage wide-content rendering."""

            __version__ = "1.0.0"
            __all__ = ["process", "summarize"]


            def process(data: list[dict]) -> list[dict]:
                """
                Process a list of records.

                Parameters
                ----------
                data
                    A list of dictionaries representing data records.

                Returns
                -------
                list[dict]
                    The processed records with added metadata fields.
                """
                return [
                    {**record, "processed": True}
                    for record in data
                ]


            def summarize(data: list[dict], group_by: str = "category") -> dict:
                """
                Summarize data records by a grouping key.

                Parameters
                ----------
                data
                    A list of dictionaries to summarize.
                group_by
                    The key to group records by.

                Returns
                -------
                dict
                    A dictionary mapping group keys to record counts.
                """
                result: dict[str, int] = {}
                for record in data:
                    key = record.get(group_by, "unknown")
                    result[key] = result.get(key, 0) + 1
                return result
        ''',
        "README.md": """\
            # gdtest-homepage-wide

            A test package for verifying that wide content on the homepage
            renders at full width even when the column-margin metadata
            sidebar is present.

            ## Installation

            ```bash
            pip install gdtest-homepage-wide
            ```

            ## Quick Start

            The following code block is deliberately wide to test layout:

            ```python
            from gdtest_homepage_wide import process, summarize

            # Build a dataset with many columns to produce a wide display
            data = [
                {"id": 1, "category": "widgets",  "name": "Widget A",   "price": 9.99,  "quantity": 100, "warehouse": "East",  "status": "active",   "rating": 4.5},
                {"id": 2, "category": "gadgets",  "name": "Gadget B",   "price": 24.99, "quantity": 50,  "warehouse": "West",  "status": "active",   "rating": 4.2},
                {"id": 3, "category": "widgets",  "name": "Widget C",   "price": 14.99, "quantity": 200, "warehouse": "North", "status": "inactive", "rating": 3.8},
                {"id": 4, "category": "gadgets",  "name": "Gadget D",   "price": 49.99, "quantity": 25,  "warehouse": "South", "status": "active",   "rating": 4.9},
                {"id": 5, "category": "doohickeys", "name": "Doohickey E", "price": 5.99,  "quantity": 500, "warehouse": "East",  "status": "active",   "rating": 3.5},
            ]

            processed = process(data)
            summary = summarize(processed, group_by="category")
            print(summary)  # => {'widgets': 2, 'gadgets': 2, 'doohickeys': 1}
            ```

            ## Wide Table

            | ID | Category   | Name        | Price  | Quantity | Warehouse | Status   | Rating | Last Updated       | Notes                          |
            |----|------------|-------------|--------|----------|-----------|----------|--------|--------------------|--------------------------------|
            | 1  | widgets    | Widget A    | $9.99  | 100      | East      | active   | 4.5    | 2025-01-15 08:30   | Best seller in Q4              |
            | 2  | gadgets    | Gadget B    | $24.99 | 50       | West      | active   | 4.2    | 2025-02-20 14:15   | New design launched            |
            | 3  | widgets    | Widget C    | $14.99 | 200      | North     | inactive | 3.8    | 2025-01-10 09:00   | Discontinued next quarter      |
            | 4  | gadgets    | Gadget D    | $49.99 | 25       | South     | active   | 4.9    | 2025-03-01 11:45   | Premium line                   |
            | 5  | doohickeys | Doohickey E | $5.99  | 500      | East      | active   | 3.5    | 2025-02-28 16:30   | High volume, low margin        |

            ## Usage Details

            Process records to add metadata, then summarize by any key:

            ```python
            summary = summarize(processed, group_by="warehouse")
            # => {'East': 2, 'West': 1, 'North': 1, 'South': 1}
            ```

            This text paragraph after the table and code blocks should
            also render at normal width without indentation.
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-homepage-wide",
        "detected_module": "gdtest_homepage_wide",
        "detected_parser": "numpy",
        "export_names": ["process", "summarize"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
