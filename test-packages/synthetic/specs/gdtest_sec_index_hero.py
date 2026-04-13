"""
gdtest_sec_index_hero — Section index pages with hero images.

Dimensions: N10
Focus: Enhanced section index pages where some entries have hero images
       (rendered as image cards in a grid) and some are plain links.
       Tests both 2-column and 1-column image card layouts.
"""

# Inline SVG hero images (data URIs so they render without external files)
_HERO_BLUE = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='600' height='300'%3E%3Crect fill='%234A90D9' width='600' height='300'/%3E"
    "%3Ctext x='300' y='160' text-anchor='middle' fill='white' "
    "font-size='28' font-family='sans-serif'%3EStarter Demo%3C/text%3E%3C/svg%3E"
)
_HERO_GREEN = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='600' height='300'%3E%3Crect fill='%2342B883' width='600' height='300'/%3E"
    "%3Ctext x='300' y='160' text-anchor='middle' fill='white' "
    "font-size='28' font-family='sans-serif'%3EAdvanced Demo%3C/text%3E%3C/svg%3E"
)
_HERO_ORANGE = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='600' height='300'%3E%3Crect fill='%23E8853D' width='600' height='300'/%3E"
    "%3Ctext x='300' y='160' text-anchor='middle' fill='white' "
    "font-size='28' font-family='sans-serif'%3EData Pipeline%3C/text%3E%3C/svg%3E"
)
_HERO_PURPLE = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='600' height='300'%3E%3Crect fill='%237C4DFF' width='600' height='300'/%3E"
    "%3Ctext x='300' y='160' text-anchor='middle' fill='white' "
    "font-size='28' font-family='sans-serif'%3EVisualization%3C/text%3E%3C/svg%3E"
)
_HERO_RED = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='600' height='300'%3E%3Crect fill='%23E53935' width='600' height='300'/%3E"
    "%3Ctext x='300' y='160' text-anchor='middle' fill='white' "
    "font-size='28' font-family='sans-serif'%3EReal-Time%3C/text%3E%3C/svg%3E"
)
_HERO_TEAL = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='600' height='300'%3E%3Crect fill='%23009688' width='600' height='300'/%3E"
    "%3Ctext x='300' y='160' text-anchor='middle' fill='white' "
    "font-size='28' font-family='sans-serif'%3EWorkflow%3C/text%3E%3C/svg%3E"
)

SPEC = {
    "name": "gdtest_sec_index_hero",
    "description": (
        "Section index pages with hero images: 2-col demos (mixed image + plain) "
        "and 1-col gallery (all images)."
    ),
    "dimensions": ["N10"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-index-hero",
            "version": "1.0.0",
            "description": "Testing enhanced section index pages with hero images.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {
                "title": "Demos",
                "dir": "demos",
                "index": True,
                # default index_columns: 2 — featured items with images in 2-col grid,
                # plain entries below as single-column list
            },
            {
                "title": "Gallery",
                "dir": "gallery",
                "index": True,
                "index_columns": 1,
                "navbar_after": "Demos",
            },
        ],
    },
    "files": {
        # ── Package source ──
        "gdtest_sec_index_hero/__init__.py": (
            '"""Test package for section index hero cards."""\n\n'
            "from .core import process, summarize, validate\n\n"
            '__all__ = ["process", "summarize", "validate"]\n'
        ),
        "gdtest_sec_index_hero/core.py": '''
            """Core processing functions."""


            def process(data: list, *, strict: bool = False) -> list:
                """Process a list of values.

                Parameters
                ----------
                data : list
                    Input values to process.
                strict : bool
                    If True, raise on invalid values.

                Returns
                -------
                list
                    Processed values.

                Examples
                --------
                >>> process([1, 2, 3])
                [1, 2, 3]
                """
                return [x for x in data if x is not None] if strict else list(data)


            def summarize(values: list) -> dict:
                """Summarize a list of numeric values.

                Parameters
                ----------
                values : list
                    Numeric values to summarize.

                Returns
                -------
                dict
                    Summary with count, sum, and mean.

                Examples
                --------
                >>> summarize([10, 20, 30])
                {'count': 3, 'sum': 60, 'mean': 20.0}
                """
                n = len(values)
                total = sum(values)
                return {"count": n, "sum": total, "mean": total / n if n else 0}


            def validate(schema: dict, record: dict) -> bool:
                """Validate a record against a schema.

                Parameters
                ----------
                schema : dict
                    Expected field names mapped to types.
                record : dict
                    The record to validate.

                Returns
                -------
                bool
                    True if the record conforms to the schema.

                Examples
                --------
                >>> validate({"name": str}, {"name": "Alice"})
                True
                """
                for key, expected_type in schema.items():
                    if key not in record or not isinstance(record[key], expected_type):
                        return False
                return True
        ''',
        # ── Demos section (2-column, mixed images + plain) ──
        # Featured demos WITH hero images (appear as image cards)
        "demos/01-starter-demo.qmd": (
            "---\n"
            "title: Starter Demo\n"
            "description: A minimal example showing the basics of data processing.\n"
            f'image: "{_HERO_BLUE}"\n'
            "---\n"
            "\n"
            "# Starter Demo\n"
            "\n"
            "This demo walks through the most basic usage of the package.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process\n"
            "\n"
            "result = process([1, 2, None, 3], strict=True)\n"
            "print(result)  # [1, 2, 3]\n"
            "```\n"
            "\n"
            "The `strict` parameter filters out `None` values, giving you a clean list.\n"
        ),
        "demos/02-advanced-demo.qmd": (
            "---\n"
            "title: Advanced Demo\n"
            "description: A comprehensive example with chained operations and validation.\n"
            f'image: "{_HERO_GREEN}"\n'
            "---\n"
            "\n"
            "# Advanced Demo\n"
            "\n"
            "This demo chains multiple operations together.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process, summarize, validate\n"
            "\n"
            "data = process([10, 20, None, 30, 40], strict=True)\n"
            "stats = summarize(data)\n"
            "print(stats)  # {'count': 4, 'sum': 100, 'mean': 25.0}\n"
            "\n"
            "schema = {'count': int, 'sum': int, 'mean': float}\n"
            "assert validate(schema, stats)\n"
            "```\n"
        ),
        "demos/03-data-pipeline.qmd": (
            "---\n"
            "title: Data Pipeline\n"
            "description: Build a complete ETL pipeline from raw data to validated output.\n"
            f'image: "{_HERO_ORANGE}"\n'
            "---\n"
            "\n"
            "# Data Pipeline\n"
            "\n"
            "A step-by-step guide to building a data pipeline.\n"
            "\n"
            "## Step 1: Extract\n"
            "\n"
            "```python\n"
            "raw = [100, None, 200, None, 300]\n"
            "```\n"
            "\n"
            "## Step 2: Transform\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process\n"
            "clean = process(raw, strict=True)  # [100, 200, 300]\n"
            "```\n"
            "\n"
            "## Step 3: Load\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import summarize\n"
            "output = summarize(clean)\n"
            "print(output)  # {'count': 3, 'sum': 600, 'mean': 200.0}\n"
            "```\n"
        ),
        "demos/04-visualization.qmd": (
            "---\n"
            "title: Visualization\n"
            "description: Create summary visualizations from processed data.\n"
            f'image: "{_HERO_PURPLE}"\n'
            "---\n"
            "\n"
            "# Visualization\n"
            "\n"
            "After processing and summarizing data, you can visualize the results.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process, summarize\n"
            "\n"
            "data = process([5, 15, 25, 35, 45])\n"
            "stats = summarize(data)\n"
            "print(f\"Mean: {stats['mean']}, Total: {stats['sum']}\")\n"
            "```\n"
            "\n"
            "Use these summary statistics as input to your favorite plotting library.\n"
        ),
        # Plain demos WITHOUT images (appear as simple link list below the cards)
        "demos/05-error-handling.qmd": (
            "---\n"
            "title: Error Handling\n"
            "description: Learn how to handle edge cases and invalid inputs gracefully.\n"
            "---\n"
            "\n"
            "# Error Handling\n"
            "\n"
            "When working with real-world data you need to handle edge cases.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process, validate\n"
            "\n"
            "# Empty lists are handled cleanly\n"
            "result = process([], strict=True)\n"
            "print(result)  # []\n"
            "\n"
            "# Validation catches missing fields\n"
            "assert not validate({'name': str}, {'age': 30})\n"
            "```\n"
        ),
        "demos/06-batch-processing.qmd": (
            "---\n"
            "title: Batch Processing\n"
            "description: Process multiple datasets in batch mode.\n"
            "---\n"
            "\n"
            "# Batch Processing\n"
            "\n"
            "Process several datasets at once.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process, summarize\n"
            "\n"
            "datasets = [\n"
            "    [10, 20, 30],\n"
            "    [5, None, 15],\n"
            "    [100, 200, 300],\n"
            "]\n"
            "\n"
            "for ds in datasets:\n"
            "    clean = process(ds, strict=True)\n"
            "    print(summarize(clean))\n"
            "```\n"
        ),
        "demos/07-schema-patterns.qmd": (
            "---\n"
            "title: Common Schema Patterns\n"
            "description: Reusable validation schemas for typical data structures.\n"
            "---\n"
            "\n"
            "# Common Schema Patterns\n"
            "\n"
            "Define reusable schemas for common record types.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import validate\n"
            "\n"
            "user_schema = {'name': str, 'age': int}\n"
            "event_schema = {'type': str, 'timestamp': float}\n"
            "\n"
            "assert validate(user_schema, {'name': 'Alice', 'age': 30})\n"
            "assert validate(event_schema, {'type': 'click', 'timestamp': 1.0})\n"
            "```\n"
        ),
        "demos/08-performance-tips.qmd": (
            "---\n"
            "title: Performance Tips\n"
            "description: Optimize processing speed for large datasets.\n"
            "---\n"
            "\n"
            "# Performance Tips\n"
            "\n"
            "Tips for working efficiently with large volumes of data.\n"
            "\n"
            "- Use `strict=False` (the default) when you know data is clean\n"
            "- Pre-validate schemas once, then batch-process records\n"
            "- Use `summarize()` to get aggregate stats without storing intermediates\n"
        ),
        "demos/09-integration-guide.qmd": (
            "---\n"
            "title: Integration Guide\n"
            "description: Integrate the package with pandas, Polars, and other frameworks.\n"
            "---\n"
            "\n"
            "# Integration Guide\n"
            "\n"
            "How to use this package alongside popular data frameworks.\n"
            "\n"
            "## With plain Python\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process\n"
            "result = process([1, 2, 3])\n"
            "```\n"
            "\n"
            "## Converting results\n"
            "\n"
            "The `summarize()` function returns a plain dict, making it easy\n"
            "to convert to any format you need.\n"
        ),
        "demos/10-custom-validators.qmd": (
            "---\n"
            "title: Custom Validators\n"
            "description: Build your own validation logic on top of the validate function.\n"
            "---\n"
            "\n"
            "# Custom Validators\n"
            "\n"
            "Extend the built-in `validate()` with custom rules.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import validate\n"
            "\n"
            "def validate_positive(record):\n"
            "    base_ok = validate({'value': int}, record)\n"
            "    return base_ok and record['value'] > 0\n"
            "\n"
            "assert validate_positive({'value': 42})\n"
            "assert not validate_positive({'value': -1})\n"
            "```\n"
        ),
        # ── Gallery section (1-column, all pages have images) ──
        "gallery/01-real-time-dashboard.qmd": (
            "---\n"
            "title: Real-Time Dashboard\n"
            "description: A live dashboard that processes streaming data and displays rolling statistics.\n"
            f'image: "{_HERO_RED}"\n'
            "---\n"
            "\n"
            "# Real-Time Dashboard\n"
            "\n"
            "This example shows a dashboard that consumes a data stream,\n"
            "processes each batch, and updates summary statistics in real time.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process, summarize\n"
            "\n"
            "# Simulate a streaming batch\n"
            "batch = [42, None, 87, 13, None, 65]\n"
            "clean = process(batch, strict=True)\n"
            "stats = summarize(clean)\n"
            "print(stats)\n"
            "```\n"
        ),
        "gallery/02-workflow-automation.qmd": (
            "---\n"
            "title: Workflow Automation\n"
            "description: An automated pipeline that validates, processes, and reports on incoming records.\n"
            f'image: "{_HERO_TEAL}"\n'
            "---\n"
            "\n"
            "# Workflow Automation\n"
            "\n"
            "Automate your data quality workflow end to end.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import validate, process, summarize\n"
            "\n"
            "schema = {'value': int}\n"
            "records = [{'value': 10}, {'value': 20}, {'value': 30}]\n"
            "\n"
            "valid = [r for r in records if validate(schema, r)]\n"
            "values = [r['value'] for r in valid]\n"
            "clean = process(values, strict=True)\n"
            "report = summarize(clean)\n"
            "print(report)\n"
            "```\n"
        ),
        "gallery/03-data-explorer.qmd": (
            "---\n"
            "title: Data Explorer\n"
            "description: An interactive data exploration tool that lets you filter, summarize, and drill down.\n"
            f'image: "{_HERO_PURPLE}"\n'
            "---\n"
            "\n"
            "# Data Explorer\n"
            "\n"
            "Explore datasets interactively by processing subsets and reviewing statistics.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import process, summarize\n"
            "\n"
            "dataset = [5, 10, 15, 20, 25, 30, 35, 40]\n"
            "\n"
            "# Filter to values above 15\n"
            "subset = [x for x in process(dataset) if x > 15]\n"
            "print(summarize(subset))\n"
            "```\n"
        ),
        "gallery/04-quality-report.qmd": (
            "---\n"
            "title: Quality Report\n"
            "description: Generate a comprehensive data quality report with validation summaries.\n"
            f'image: "{_HERO_BLUE}"\n'
            "---\n"
            "\n"
            "# Quality Report\n"
            "\n"
            "Produce a data quality report by validating every record.\n"
            "\n"
            "```python\n"
            "from gdtest_sec_index_hero import validate\n"
            "\n"
            "schema = {'name': str, 'score': int}\n"
            "records = [\n"
            "    {'name': 'Alice', 'score': 95},\n"
            "    {'name': 'Bob'},\n"
            "    {'name': 'Carol', 'score': 88},\n"
            "]\n"
            "\n"
            "passed = sum(1 for r in records if validate(schema, r))\n"
            'print(f"{passed}/{len(records)} records valid")\n'
            "```\n"
        ),
        # ── README ──
        "README.md": (
            "# gdtest-sec-index-hero\n"
            "\n"
            "Test package demonstrating enhanced section index pages with hero images.\n"
            "\n"
            "- **Demos**: 2-column layout with 4 featured image cards + 6 plain links\n"
            "- **Gallery**: 1-column layout with 4 full-width image cards\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-sec-index-hero",
        "detected_module": "gdtest_sec_index_hero",
        "detected_parser": "numpy",
        "export_names": ["process", "summarize", "validate"],
        "num_exports": 3,
    },
}
