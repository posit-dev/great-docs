"""
gdtest_gt_tables — Great Tables vs. Markdown tables rendering.

Dimensions: G7, M4, N1
Focus: Exercises the full rendering pipeline for Great Tables (GT) output
       alongside conventional Markdown tables to verify:

       1. GT tables preserve their ``<colgroup>`` tags (post-render.py
          ``strip_colgroup_tags`` skips tables with class ``gt_table``).
       2. GT tables are NOT wrapped in ``gd-table-responsive`` (the
          responsive-tables.js ``wrapTable`` function skips ``gt_table``).
       3. GT tables are NOT affected by Bootstrap ``.table-bordered``
          (great-docs.scss uses ``table:not(.gt_table)``).
       4. Conventional Markdown tables still get responsive wrapping and
          Bootstrap-based styling as expected.
"""

SPEC = {
    "name": "gdtest_gt_tables",
    "description": ("GT tables rendering alongside Markdown tables"),
    "dimensions": ["G7", "M4", "N1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-gt-tables",
            "version": "0.1.0",
            "description": "Test Great Tables and Markdown tables rendering",
            "dependencies": ["great_tables"],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {},
    "files": {
        # ── Project root ──────────────────────────────────────────────────
        "README.md": ("# gdtest-gt-tables\n\nTest Great Tables and Markdown tables rendering.\n"),
        # ── Package source ────────────────────────────────────────────────
        "gdtest_gt_tables/__init__.py": '''\
            """A test package for GT table rendering."""

            __version__ = "0.1.0"
            __all__ = ["make_gt_table", "summarize"]


            def make_gt_table():
                """
                Create a sample Great Tables table.

                Returns
                -------
                GT
                    A styled GT table object.

                Examples
                --------
                ```{python}
                from gdtest_gt_tables import make_gt_table
                make_gt_table()
                ```
                """
                from great_tables import GT
                import pandas as pd

                df = pd.DataFrame({
                    "Name": ["Alice", "Bob", "Charlie"],
                    "Score": [95, 87, 92],
                    "Grade": ["A", "B+", "A-"],
                })
                return GT(df)


            def summarize(data: list) -> dict:
                """
                Summarize a list of numbers.

                Parameters
                ----------
                data
                    List of numeric values.

                Returns
                -------
                dict
                    Summary statistics with keys ``mean``, ``total``, ``count``.
                """
                return {
                    "mean": sum(data) / len(data),
                    "total": sum(data),
                    "count": len(data),
                }
        ''',
        # ── User guide: GT table page ─────────────────────────────────────
        "user_guide/01-gt-tables.qmd": (
            "---\n"
            "title: Great Tables Output\n"
            "---\n"
            "\n"
            "## A GT Table with Fixed Column Widths\n"
            "\n"
            "This page renders a Great Tables table with explicit column widths,\n"
            "which produces a `<colgroup>` element that must be preserved.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    "Name": ["Alice", "Bob", "Charlie", "Diana"],\n'
            '    "Score": [95, 87, 92, 78],\n'
            '    "Grade": ["A", "B+", "A-", "C+"],\n'
            '    "Status": ["Pass", "Pass", "Pass", "Pass"],\n'
            "})\n"
            "\n"
            "(\n"
            "    GT(df, id='gt_fixed')\n"
            '    .tab_header(title="Student Grades", subtitle="Fall 2025")\n'
            '    .cols_width(Name="150px", Score="80px", Grade="80px", Status="80px")\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
            "\n"
            "## A GT Table without Fixed Widths\n"
            "\n"
            "This table uses default column sizing (no colgroup).\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df2 = pd.DataFrame({\n"
            '    "Feature": ["Responsive", "Dark mode", "Scroll"],\n'
            '    "Supported": ["Yes", "Yes", "Yes"],\n'
            "})\n"
            "\n"
            "GT(df2, id='gt_auto').tab_options(quarto_disable_processing=True)\n"
            "```\n"
        ),
        # ── User guide: Markdown table page ───────────────────────────────
        "user_guide/02-markdown-tables.qmd": (
            "---\n"
            "title: Markdown Tables\n"
            "---\n"
            "\n"
            "## A Standard Markdown Table\n"
            "\n"
            "This page has a conventional Markdown table that should get\n"
            "responsive wrapping and Bootstrap table styling.\n"
            "\n"
            "| Name    | Score | Grade | Status |\n"
            "|---------|-------|-------|--------|\n"
            "| Alice   | 95    | A     | Pass   |\n"
            "| Bob     | 87    | B+    | Pass   |\n"
            "| Charlie | 92    | A-    | Pass   |\n"
            "| Diana   | 78    | C+    | Pass   |\n"
            "\n"
            "The table above should:\n"
            "\n"
            "- Be wrapped in a `gd-table-responsive` div\n"
            "- NOT have a `<colgroup>` element\n"
            "- Receive Bootstrap `.table-bordered` styling\n"
            "\n"
            "## A Second Table\n"
            "\n"
            "| Feature     | Supported |\n"
            "|-------------|-----------|\n"
            "| Responsive  | Yes       |\n"
            "| Dark mode   | Yes       |\n"
            "| Scroll      | Yes       |\n"
        ),
        # ── User guide: GT table with page-level Quarto opt-out ─────────
        "user_guide/03-gt-page-level.qmd": (
            "---\n"
            "title: GT with Page-Level Processing Disabled\n"
            "jupyter: python3\n"
            "html-table-processing: none\n"
            "---\n"
            "\n"
            "## GT Table (page-level `html-table-processing: none`)\n"
            "\n"
            "This page uses the YAML frontmatter option\n"
            "`html-table-processing: none` to disable Quarto's table\n"
            "processing at the page level, rather than per-table with\n"
            "`tab_options(quarto_disable_processing=True)`.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    "City": ["London", "Paris", "Tokyo", "Sydney"],\n'
            '    "Population": [8_982_000, 2_161_000, 13_960_000, 5_312_000],\n'
            '    "Area_km2": [1_572, 105, 2_194, 12_368],\n'
            "})\n"
            "\n"
            "(\n"
            "    GT(df, id='gt_page_level')\n"
            '    .tab_header(title="World Cities", subtitle="Population & Area")\n'
            '    .cols_width(City="120px", Population="120px", Area_km2="100px")\n'
            ")\n"
            "```\n"
            "\n"
            "## Markdown Table on the Same Page\n"
            "\n"
            "This Markdown table is also on the page with\n"
            "`html-table-processing: none`, so it should also be free\n"
            "of Quarto's Bootstrap table classes.\n"
            "\n"
            "| City    | Country   |\n"
            "|---------|-----------|\n"
            "| London  | UK        |\n"
            "| Paris   | France    |\n"
            "| Tokyo   | Japan     |\n"
        ),
    },
    "expected": {
        "user_guide_pages": [
            "gt-tables.html",
            "markdown-tables.html",
            "gt-page-level.html",
        ],
        "reference_pages": [
            "make_gt_table.html",
            "summarize.html",
        ],
        "exports": ["make_gt_table", "summarize"],
    },
}
