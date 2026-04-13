"""
gdtest_scale_to_fit — Scale-to-fit auto-scaling for wide HTML output.

Dimensions: G7, M4, N1
Focus: Exercises the 3-level scale-to-fit configuration system by rendering
       GT tables of varying widths and a custom ``_repr_html_`` object.

       1. **Global config** (``scale_to_fit: ["#wide_gt", "#custom_html"]``):
          The ``great-docs.yml`` targets specific element IDs for auto-scaling.
       2. **Page-level frontmatter** (``scale-to-fit: ["#page_gt"]``):
          One page overrides the global selectors so only ``#page_gt`` scales.
       3. **Manual div** (``:::{.scale-to-fit}``):
          One page wraps output in a ``.scale-to-fit`` div manually.
       4. **No-scale page**: A narrow GT table that matches no selectors,
          verifying that tables which don't match aren't affected.

       Verification targets:
       - ``gd-scale-to-fit`` meta tag present in ``<head>`` (global config)
       - ``gd-scale-to-fit-page`` meta tag present only on page-override page
       - ``.scale-to-fit`` class on auto-targeted containers
       - ``.gd-scale-wrapper`` div inside scaled containers
       - Non-targeted elements have no scale-to-fit classes
       - ID-based targeting works (``#wide_gt`` scaled, ``#narrow_gt`` not)
"""

SPEC = {
    "name": "gdtest_scale_to_fit",
    "description": "Scale-to-fit config system for wide HTML output",
    "dimensions": ["G7", "M4", "N1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-scale-to-fit",
            "version": "0.1.0",
            "description": "Test scale-to-fit auto-scaling for wide tables",
            "dependencies": ["great_tables"],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "scale_to_fit": ["#wide_gt", "#custom_html"],
        "scale_to_fit_min_scale": "tablet",
    },
    "files": {
        # ── Project root ──────────────────────────────────────────────────
        "README.md": (
            "# gdtest-scale-to-fit\n\nTest the 3-level scale-to-fit system for wide HTML output.\n"
        ),
        # ── Package source ────────────────────────────────────────────────
        "gdtest_scale_to_fit/__init__.py": '''\
            """A test package for scale-to-fit auto-scaling."""

            __version__ = "0.1.0"
            __all__ = [
                "make_wide_table",
                "make_narrow_table",
                "make_medium_table",
                "CustomWidget",
            ]


            def make_wide_table():
                """
                Create a wide GT table with 12 columns.

                Returns
                -------
                GT
                    A GT table with many columns that overflows its container.

                Examples
                --------
                ```{python}
                from gdtest_scale_to_fit import make_wide_table
                make_wide_table()
                ```
                """
                from great_tables import GT
                import pandas as pd

                df = pd.DataFrame({
                    f"Col_{i:02d}": [f"val_{r}_{i}" for r in range(4)]
                    for i in range(1, 13)
                })
                return (
                    GT(df, id="wide_gt")
                    .tab_header(title="Wide Table (12 cols)")
                    .cols_width(**{f"Col_{i:02d}": "110px" for i in range(1, 13)})
                    .tab_options(quarto_disable_processing=True)
                )


            def make_narrow_table():
                """
                Create a narrow GT table with 3 columns.

                Returns
                -------
                GT
                    A GT table that fits comfortably in its container.
                """
                from great_tables import GT
                import pandas as pd

                df = pd.DataFrame({
                    "Name": ["Alice", "Bob"],
                    "Score": [95, 87],
                    "Grade": ["A", "B+"],
                })
                return (
                    GT(df, id="narrow_gt")
                    .tab_header(title="Narrow Table (3 cols)")
                    .tab_options(quarto_disable_processing=True)
                )


            def make_medium_table():
                """
                Create a medium GT table with 8 columns.

                Returns
                -------
                GT
                    A GT table that is moderately wide.
                """
                from great_tables import GT
                import pandas as pd

                df = pd.DataFrame({
                    f"Metric_{i}": [round(i * 1.5 + r * 0.3, 1) for r in range(5)]
                    for i in range(1, 9)
                })
                return (
                    GT(df, id="medium_gt")
                    .tab_header(title="Medium Table (8 cols)")
                    .cols_width(**{f"Metric_{i}": "120px" for i in range(1, 9)})
                    .tab_options(quarto_disable_processing=True)
                )


            class CustomWidget:
                """
                A custom widget with ``_repr_html_`` for scale-to-fit testing.

                This produces a wide HTML block that is NOT a GT table, verifying
                that scale-to-fit works for arbitrary ``_repr_html_`` objects.

                Parameters
                ----------
                width
                    CSS width of the widget (e.g., ``"1500px"``).
                widget_id
                    HTML ``id`` attribute for targeting.
                """

                def __init__(self, width: str = "1500px", widget_id: str = "custom_html"):
                    self.width = width
                    self.widget_id = widget_id

                def _repr_html_(self) -> str:
                    """Render as wide HTML block."""
                    return (
                        f'<div id="{self.widget_id}" '
                        f'style="width:{self.width};background:#e8f4fd;'
                        f'border:2px solid #2196F3;padding:16px;'
                        f'font-family:monospace;">'
                        f'<strong>CustomWidget</strong> &mdash; '
                        f'width: {self.width}, id: {self.widget_id}'
                        f'</div>'
                    )
        ''',
        # ── User guide: Page 1 — Global config targeting ─────────────────
        # This page has #wide_gt and #custom_html which match the global
        # scale_to_fit config. It also has #narrow_gt which does NOT match.
        "user_guide/01-global-targeting.qmd": (
            "---\n"
            "title: Global Config Targeting\n"
            "---\n"
            "\n"
            "## Wide GT Table (12 columns)\n"
            "\n"
            'This GT table has `id="wide_gt"` and should be auto-scaled\n'
            'because the global config has `scale_to_fit: ["#wide_gt", ...]`.\n'
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"Col_{i:02d}": [f"val_{r}_{i}" for r in range(4)]\n'
            "    for i in range(1, 13)\n"
            "})\n"
            "\n"
            "(\n"
            '    GT(df, id="wide_gt")\n'
            '    .tab_header(title="Wide Table (12 cols)")\n'
            '    .cols_width(**{f"Col_{i:02d}": "110px" for i in range(1, 13)})\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
            "\n"
            "## Custom HTML Widget\n"
            "\n"
            'This `_repr_html_` object has `id="custom_html"` and should also\n'
            "be auto-scaled by the global config.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_scale_to_fit import CustomWidget\n"
            "CustomWidget(width='1500px', widget_id='custom_html')\n"
            "```\n"
            "\n"
            "## Narrow GT Table (not targeted)\n"
            "\n"
            'This table has `id="narrow_gt"` which is NOT in the global\n'
            "`scale_to_fit` list, so it should NOT be auto-scaled.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    "Name": ["Alice", "Bob"],\n'
            '    "Score": [95, 87],\n'
            '    "Grade": ["A", "B+"],\n'
            "})\n"
            "\n"
            "(\n"
            '    GT(df, id="narrow_gt")\n'
            '    .tab_header(title="Narrow Table (3 cols)")\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
        ),
        # ── User guide: Page 2 — Page-level override ─────────────────────
        # This page uses frontmatter `scale-to-fit: ["#page_gt"]` to override
        # the global config. Only #page_gt should be scaled; not #wide_gt_2.
        "user_guide/02-page-override.qmd": (
            "---\n"
            "title: Page-Level Override\n"
            "scale-to-fit:\n"
            '  - "#page_gt"\n'
            "scale-to-fit-min-scale: mobile\n"
            "---\n"
            "\n"
            "## Medium GT Table (page-targeted)\n"
            "\n"
            'This page has `scale-to-fit: ["#page_gt"]` in its frontmatter,\n'
            "which overrides the global config. Only `#page_gt` should scale.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"Metric_{i}": [round(i * 1.5 + r * 0.3, 1) for r in range(5)]\n'
            "    for i in range(1, 9)\n"
            "})\n"
            "\n"
            "(\n"
            '    GT(df, id="page_gt")\n'
            '    .tab_header(title="Page-Targeted Table (8 cols)")\n'
            '    .cols_width(**{f"Metric_{i}": "120px" for i in range(1, 9)})\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
            "\n"
            "## Wide GT Table (NOT targeted on this page)\n"
            "\n"
            'This table has `id="wide_gt_2"` which matches nothing on this page\n'
            "(the page override replaces the global selectors).\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"Col_{i:02d}": [f"val_{r}_{i}" for r in range(4)]\n'
            "    for i in range(1, 13)\n"
            "})\n"
            "\n"
            "(\n"
            '    GT(df, id="wide_gt_2")\n'
            '    .tab_header(title="Wide Table 2 (not targeted here)")\n'
            '    .cols_width(**{f"Col_{i:02d}": "110px" for i in range(1, 13)})\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
        ),
        # ── User guide: Page 3 — Manual div wrapping ─────────────────────
        # This page uses the manual :::{.scale-to-fit} approach; no config
        # or frontmatter involved.
        "user_guide/03-manual-div.qmd": (
            "---\n"
            "title: Manual Div Wrapping\n"
            "---\n"
            "\n"
            "## Manually Scaled Table\n"
            "\n"
            "This table is wrapped in a `:::{.scale-to-fit}` div.\n"
            "No config or frontmatter needed.\n"
            "\n"
            ":::{.scale-to-fit}\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"Field_{i}": [f"data_{r}_{i}" for r in range(3)]\n'
            "    for i in range(1, 11)\n"
            "})\n"
            "\n"
            "(\n"
            '    GT(df, id="manual_gt")\n'
            '    .tab_header(title="Manual Scale (10 cols)")\n'
            '    .cols_width(**{f"Field_{i}": "110px" for i in range(1, 11)})\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
            ":::\n"
            "\n"
            "## Unwrapped Table (for comparison)\n"
            "\n"
            "This table is NOT wrapped and NOT targeted by any selector.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"X_{i}": [i * 10 + r for r in range(3)]\n'
            "    for i in range(1, 11)\n"
            "})\n"
            "\n"
            "(\n"
            '    GT(df, id="unwrapped_gt")\n'
            '    .tab_header(title="Unwrapped Table (10 cols, no scaling)")\n'
            '    .cols_width(**{f"X_{i}": "110px" for i in range(1, 11)})\n'
            "    .tab_options(quarto_disable_processing=True)\n"
            ")\n"
            "```\n"
        ),
        # ── User guide: Page 4 — Multiple widths comparison ──────────────
        # Shows tables of 4, 8, 12, and 16 columns side-by-side with a
        # shared class selector for testing class-based targeting.
        "user_guide/04-width-comparison.qmd": (
            "---\n"
            "title: Width Comparison\n"
            "---\n"
            "\n"
            "This page shows GT tables of increasing widths for visual\n"
            "comparison. None are auto-scaled (no matching selectors).\n"
            "\n"
            "## 4-Column Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"C{i}": [f"v{r}{i}" for r in range(3)]\n'
            "    for i in range(1, 5)\n"
            "})\n"
            "GT(df, id='cmp_4').tab_header(title='4 Columns').tab_options(quarto_disable_processing=True)\n"
            "```\n"
            "\n"
            "## 8-Column Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"C{i}": [f"v{r}{i}" for r in range(3)]\n'
            "    for i in range(1, 9)\n"
            "})\n"
            "GT(df, id='cmp_8').tab_header(title='8 Columns').tab_options(quarto_disable_processing=True)\n"
            "```\n"
            "\n"
            "## 12-Column Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"C{i}": [f"v{r}{i}" for r in range(3)]\n'
            "    for i in range(1, 13)\n"
            "})\n"
            "GT(df, id='cmp_12').tab_header(title='12 Columns').tab_options(quarto_disable_processing=True)\n"
            "```\n"
            "\n"
            "## 16-Column Table\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_tables import GT\n"
            "import pandas as pd\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    f"C{i}": [f"v{r}{i}" for r in range(3)]\n'
            "    for i in range(1, 17)\n"
            "})\n"
            "GT(df, id='cmp_16').tab_header(title='16 Columns').tab_options(quarto_disable_processing=True)\n"
            "```\n"
        ),
    },
    "expected": {
        "user_guide_pages": [
            "global-targeting.html",
            "page-override.html",
            "manual-div.html",
            "width-comparison.html",
        ],
        "reference_pages": [
            "make_wide_table.html",
            "make_narrow_table.html",
            "make_medium_table.html",
            "CustomWidget.html",
        ],
        "exports": [
            "make_wide_table",
            "make_narrow_table",
            "make_medium_table",
            "CustomWidget",
        ],
        # ── Scale-to-fit verification keys ────────────────────────────────
        # Global config selectors (applied to all pages unless overridden)
        "global_scale_selectors": ["#wide_gt", "#custom_html"],
        # Global minimum scale threshold (keyword)
        "global_min_scale": "tablet",
        # Page-level override selectors (page-override.html only)
        "page_override_selectors": ["#page_gt"],
        # Page-level override minimum scale (keyword)
        "page_override_min_scale": "mobile",
        # IDs that SHOULD be auto-scaled on global-targeting page
        "scaled_ids_global_page": ["wide_gt", "custom_html"],
        # IDs that should NOT be auto-scaled on global-targeting page
        "unscaled_ids_global_page": ["narrow_gt"],
        # IDs that SHOULD be scaled on page-override page
        "scaled_ids_override_page": ["page_gt"],
        # IDs that should NOT be scaled on page-override page
        "unscaled_ids_override_page": ["wide_gt_2"],
        # Manual div page: #manual_gt is inside .scale-to-fit div
        "manual_div_id": "manual_gt",
        # Manual div page: #unwrapped_gt is NOT inside .scale-to-fit
        "unwrapped_id": "unwrapped_gt",
    },
}
