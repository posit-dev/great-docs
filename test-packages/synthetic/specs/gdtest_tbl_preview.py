"""
gdtest_tbl_preview — Table preview showcase.

Dimensions: A1, B1, C1, D1, M4, G1
Focus: Exercises the ``tbl_preview()`` function with many different table
       shapes, data types, and display options. The user guide has twelve
       pages:

       1. Basic preview — dict and list-of-dicts, caption.
       2. Pandas tables — Pandas DataFrame, custom head/tail, show_all.
       3. Polars tables — Polars DataFrame, head-only.
       4. Missing values — None/NaN highlighting on/off, mixed types.
       5. Column options — column subsets, wide tables, hide row numbers/dtypes.
       6. All options — minimal/full chrome, custom widths, side-by-side.
       7. Text-heavy tables — long strings, ellipsis, max_col_width.
       8. TSV files — tab-delimited file reading.
       9. JSONL files — newline-delimited JSON, .ndjson alias.
       10. Parquet files — Apache Parquet columnar format.
       11. Feather & Arrow IPC — Feather files, .arrow/.ipc extensions.
       12. PyArrow tables — in-memory pyarrow.Table objects.

       The API reference documents helper functions that generate sample
       data for the previews.
"""

SPEC = {
    "name": "gdtest_tbl_preview",
    "description": "Table preview showcase with diverse table types and options.",
    "dimensions": ["A1", "B1", "C1", "D1", "M2", "G1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-tbl-preview",
            "version": "0.1.0",
            "description": "Showcase for the tbl_preview() table preview feature",
            "dependencies": ["great_docs"],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {},
    "files": {
        # ── Project root ──────────────────────────────────────────────────
        "README.md": (
            "# gdtest-tbl-preview\n\n"
            "A showcase site demonstrating the `tbl_preview()` function from\n"
            "Great Docs. Each user-guide page exercises a different combination\n"
            "of data sources, table shapes, and display options.\n"
        ),
        # ── Package source ────────────────────────────────────────────────
        "gdtest_tbl_preview/__init__.py": '''\
            """Sample data generators for table preview demos."""

            __version__ = "0.1.0"
            __all__ = [
                "sample_scores",
                "sample_inventory",
                "sample_wide",
                "sample_missing",
                "sample_types",
            ]

            from .data import (
                sample_scores,
                sample_inventory,
                sample_wide,
                sample_missing,
                sample_types,
            )
        ''',
        "gdtest_tbl_preview/data.py": '''\
            """Functions that generate sample data for preview demos."""

            from __future__ import annotations


            def sample_scores(n: int = 20) -> dict[str, list]:
                """
                Generate a student scores dataset.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with name, subject, score, grade, and
                    pass/fail columns.

                Examples
                --------
                >>> data = sample_scores(5)
                >>> len(data["name"])
                5
                """
                import random
                random.seed(42)
                names = ["Alice", "Bob", "Charlie", "Diana", "Eve",
                         "Frank", "Grace", "Hank", "Iris", "Jack"]
                subjects = ["Math", "Science", "English", "History", "Art"]
                grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "F"]
                rows_name = [random.choice(names) for _ in range(n)]
                rows_subj = [random.choice(subjects) for _ in range(n)]
                rows_score = [round(random.uniform(40, 100), 1) for _ in range(n)]
                rows_grade = [random.choice(grades) for _ in range(n)]
                rows_pass = [s >= 60.0 for s in rows_score]
                return {
                    "name": rows_name,
                    "subject": rows_subj,
                    "score": rows_score,
                    "grade": rows_grade,
                    "passed": rows_pass,
                }


            def sample_inventory(n: int = 30) -> dict[str, list]:
                """
                Generate a product inventory dataset.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with product, category, price, stock,
                    and rating columns.

                Examples
                --------
                >>> data = sample_inventory(10)
                >>> len(data["product"])
                10
                """
                import random
                random.seed(99)
                products = [
                    "Widget", "Gadget", "Doohickey", "Thingamajig",
                    "Gizmo", "Whatchamacallit", "Contraption", "Apparatus",
                ]
                categories = ["Electronics", "Tools", "Kitchen", "Garden", "Office"]
                rows_prod = [random.choice(products) for _ in range(n)]
                rows_cat = [random.choice(categories) for _ in range(n)]
                rows_price = [round(random.uniform(5.0, 200.0), 2) for _ in range(n)]
                rows_stock = [random.randint(0, 500) for _ in range(n)]
                rows_rating = [round(random.uniform(1.0, 5.0), 1) for _ in range(n)]
                return {
                    "product": rows_prod,
                    "category": rows_cat,
                    "price": rows_price,
                    "stock": rows_stock,
                    "rating": rows_rating,
                }


            def sample_wide(n_rows: int = 15, n_cols: int = 20) -> dict[str, list]:
                """
                Generate a wide dataset with many columns.

                Parameters
                ----------
                n_rows
                    Number of rows.
                n_cols
                    Number of columns.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with columns named ``col_001``
                    through ``col_{n_cols:03d}``.

                Examples
                --------
                >>> data = sample_wide(5, 8)
                >>> len(data)
                8
                """
                import random
                random.seed(7)
                return {
                    f"col_{i+1:03d}": [round(random.gauss(0, 1), 3) for _ in range(n_rows)]
                    for i in range(n_cols)
                }


            def sample_missing(n: int = 15) -> dict[str, list]:
                """
                Generate a dataset riddled with missing values.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict where roughly 25 percent of values are
                    ``None`` or ``float('nan')``.

                Examples
                --------
                >>> data = sample_missing(10)
                >>> None in data["alpha"]
                True
                """
                import random
                import math
                random.seed(13)

                def _maybe_none(val):
                    return None if random.random() < 0.25 else val

                return {
                    "alpha": [_maybe_none(random.choice(["foo", "bar", "baz"])) for _ in range(n)],
                    "beta": [_maybe_none(round(random.gauss(50, 15), 2)) for _ in range(n)],
                    "gamma": [
                        float("nan") if random.random() < 0.2 else random.randint(1, 100)
                        for _ in range(n)
                    ],
                    "delta": [_maybe_none(random.choice([True, False])) for _ in range(n)],
                }


            def sample_types() -> dict[str, list]:
                """
                Generate a dataset that exercises many Python types.

                Returns
                -------
                dict[str, list]
                    Six rows with int, float, bool, string, None, and large-number
                    columns.

                Examples
                --------
                >>> data = sample_types()
                >>> len(data["integer"])
                6
                """
                return {
                    "integer": [0, 1, -42, 1_000_000, 2**31, None],
                    "floating": [0.0, 3.14, -2.718, 1e10, float("inf"), float("nan")],
                    "boolean": [True, False, True, False, None, True],
                    "text": ["hello", "world", "", "café", "<b>bold</b>", None],
                    "big_number": [10**18, 10**15, 10**12, 10**9, 10**6, 10**3],
                }
        ''',
        # ── User guide pages (flat layout) ───────────────────────────────
        "user_guide/01-basic-preview.qmd": (
            "---\n"
            "title: Basic Preview\n"
            "---\n"
            "\n"
            "## Default Settings\n"
            "\n"
            "The simplest way to use `tbl_preview()` — pass a column-oriented\n"
            "dict and let the defaults do the work.\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "from gdtest_tbl_preview import sample_scores\n"
            "\n"
            "tbl_preview(sample_scores(20))\n"
            "```\n"
            "\n"
            "## From a List of Dicts\n"
            "\n"
            "You can also pass a list of row dicts:\n"
            "\n"
            "```{python}\n"
            "rows = [\n"
            '    {"city": "Tokyo", "pop_m": 37.4, "country": "Japan"},\n'
            '    {"city": "Delhi", "pop_m": 32.9, "country": "India"},\n'
            '    {"city": "Shanghai", "pop_m": 29.2, "country": "China"},\n'
            '    {"city": "São Paulo", "pop_m": 22.4, "country": "Brazil"},\n'
            '    {"city": "Mexico City", "pop_m": 21.8, "country": "Mexico"},\n'
            "]\n"
            "tbl_preview(rows)\n"
            "```\n"
            "\n"
            "## With a Caption\n"
            "\n"
            "```{python}\n"
            "tbl_preview(\n"
            "    sample_scores(12),\n"
            '    caption="Student Performance — Fall 2025",\n'
            ")\n"
            "```\n"
        ),
        "user_guide/02-pandas-tables.qmd": (
            "---\n"
            "title: Pandas Tables\n"
            "---\n"
            "\n"
            "## Pandas DataFrame\n"
            "\n"
            "Pass a Pandas DataFrame directly. The preview auto-detects the\n"
            "library and shows a **Pandas** badge.\n"
            "\n"
            "```{python}\n"
            "import pandas as pd\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "df = pd.DataFrame({\n"
            '    "name": ["Alice", "Bob", "Charlie", "Diana", "Eve",\n'
            '             "Frank", "Grace", "Hank", "Iris", "Jack",\n'
            '             "Kate", "Leo", "Mia", "Noah", "Olivia"],\n'
            '    "department": ["Eng", "Sales", "Eng", "HR", "Sales",\n'
            '                   "Eng", "HR", "Sales", "Eng", "HR",\n'
            '                   "Sales", "Eng", "HR", "Sales", "Eng"],\n'
            '    "salary": [95000, 72000, 88000, 65000, 78000,\n'
            "              105000, 62000, 81000, 92000, 58000,\n"
            "              74000, 110000, 67000, 83000, 97000],\n"
            '    "years": [5, 3, 7, 2, 4, 10, 1, 6, 8, 3, 4, 12, 2, 5, 9],\n'
            "})\n"
            "\n"
            "tbl_preview(df)\n"
            "```\n"
            "\n"
            "## Custom Head and Tail\n"
            "\n"
            "Show 8 rows from the top and 3 from the bottom:\n"
            "\n"
            "```{python}\n"
            "tbl_preview(df, n_head=8, n_tail=3)\n"
            "```\n"
            "\n"
            "## Show All Rows\n"
            "\n"
            "```{python}\n"
            "tbl_preview(df, show_all=True)\n"
            "```\n"
        ),
        "user_guide/03-polars-tables.qmd": (
            "---\n"
            "title: Polars Tables\n"
            "---\n"
            "\n"
            "## Polars DataFrame\n"
            "\n"
            "Polars DataFrames are detected automatically and show a blue\n"
            "**Polars** badge with precise dtype labels.\n"
            "\n"
            "```{python}\n"
            "import polars as pl\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "df = pl.DataFrame({\n"
            '    "id": range(1, 26),\n'
            '    "value": [x * 1.1 for x in range(1, 26)],\n'
            '    "category": ["A", "B", "C", "D", "E"] * 5,\n'
            '    "flag": [True, False] * 12 + [True],\n'
            "})\n"
            "\n"
            "tbl_preview(df)\n"
            "```\n"
            "\n"
            "## Head Only (No Tail)\n"
            "\n"
            "```{python}\n"
            "tbl_preview(df, n_head=10, n_tail=0)\n"
            "```\n"
        ),
        "user_guide/04-missing-values.qmd": (
            "---\n"
            "title: Missing Values\n"
            "---\n"
            "\n"
            "## Highlighted Missing Values\n"
            "\n"
            "By default, `None` and `NaN` values are highlighted in red:\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "from gdtest_tbl_preview import sample_missing\n"
            "\n"
            "tbl_preview(sample_missing(15))\n"
            "```\n"
            "\n"
            "## Without Highlighting\n"
            "\n"
            "Turn off missing-value highlighting with `highlight_missing=False`:\n"
            "\n"
            "```{python}\n"
            "tbl_preview(sample_missing(15), highlight_missing=False)\n"
            "```\n"
            "\n"
            "## Mixed Python Types\n"
            "\n"
            "Inf, NaN, None, empty strings, HTML-unsafe characters, and large\n"
            "numbers:\n"
            "\n"
            "```{python}\n"
            "from gdtest_tbl_preview import sample_types\n"
            "\n"
            "tbl_preview(sample_types(), show_all=True)\n"
            "```\n"
        ),
        "user_guide/05-column-options.qmd": (
            "---\n"
            "title: Column Options\n"
            "---\n"
            "\n"
            "## Column Subset\n"
            "\n"
            "Select and reorder columns with the `columns` parameter:\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "from gdtest_tbl_preview import sample_inventory\n"
            "\n"
            "data = sample_inventory(25)\n"
            'tbl_preview(data, columns=["product", "price", "rating"])\n'
            "```\n"
            "\n"
            "## Wide Table\n"
            "\n"
            "A table with 20 columns overflows and scrolls horizontally:\n"
            "\n"
            "```{python}\n"
            "from gdtest_tbl_preview import sample_wide\n"
            "\n"
            "tbl_preview(sample_wide(12, 20))\n"
            "```\n"
            "\n"
            "## No Row Numbers\n"
            "\n"
            "```{python}\n"
            "tbl_preview(\n"
            "    sample_inventory(10),\n"
            "    show_row_numbers=False,\n"
            ")\n"
            "```\n"
            "\n"
            "## No Dtype Labels\n"
            "\n"
            "```{python}\n"
            "tbl_preview(\n"
            "    sample_inventory(10),\n"
            "    show_dtypes=False,\n"
            ")\n"
            "```\n"
        ),
        "user_guide/06-all-options.qmd": (
            "---\n"
            "title: All Options\n"
            "---\n"
            "\n"
            "## Minimal Chrome\n"
            "\n"
            "Turn off every optional element — no row numbers, no dtypes,\n"
            "no dimension badges:\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "from gdtest_tbl_preview import sample_scores\n"
            "\n"
            "tbl_preview(\n"
            "    sample_scores(8),\n"
            "    show_row_numbers=False,\n"
            "    show_dtypes=False,\n"
            "    show_dimensions=False,\n"
            "    show_all=True,\n"
            ")\n"
            "```\n"
            "\n"
            "## Full Chrome with Caption\n"
            "\n"
            "Everything enabled plus a caption:\n"
            "\n"
            "```{python}\n"
            "tbl_preview(\n"
            "    sample_scores(50),\n"
            "    n_head=10,\n"
            "    n_tail=5,\n"
            '    caption="Top & bottom of the class roster",\n'
            ")\n"
            "```\n"
            "\n"
            "## Custom Column Width\n"
            "\n"
            "Restrict columns to 120px max width:\n"
            "\n"
            "```{python}\n"
            "tbl_preview(\n"
            "    sample_scores(15),\n"
            "    max_col_width=120,\n"
            "    min_tbl_width=400,\n"
            ")\n"
            "```\n"
            "\n"
            "## Side-by-Side Comparison\n"
            "\n"
            "Default Pandas output vs. `tbl_preview()` on the same data:\n"
            "\n"
            "::: {layout-ncol=2}\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import pandas as pd\n"
            "df = pd.DataFrame(sample_scores(10))\n"
            "df\n"
            "```\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_preview(df)\n"
            "```\n"
            "\n"
            ":::\n"
        ),
        "user_guide/07-text-heavy-tables.qmd": (
            "---\n"
            "title: Text-Heavy Tables\n"
            "---\n"
            "\n"
            "## Long Strings (Default Width)\n"
            "\n"
            "Cells with very long text are capped at `max_col_width` (250px\n"
            "by default) and show an ellipsis instead of wrapping.\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "data = {\n"
            '    "id": [1, 2, 3, 4, 5],\n'
            '    "title": [\n'
            '        "A short title",\n'
            '        "A moderately long title that tests mid-range widths",\n'
            '        "This title is intentionally very long so that it will definitely exceed the maximum column width and trigger text-overflow ellipsis behavior in the rendered table cell",\n'
            '        "Brief",\n'
            '        "Another extremely verbose title string that goes on and on to stress-test the truncation and overflow handling in the preview table renderer",\n'
            "    ],\n"
            '    "status": ["draft", "published", "review", "archived", "published"],\n'
            "}\n"
            "\n"
            "tbl_preview(data, show_all=True)\n"
            "```\n"
            "\n"
            "## Descriptions and Paragraphs\n"
            "\n"
            "Real-world data often has paragraph-length text in columns.\n"
            "\n"
            "```{python}\n"
            "data = {\n"
            '    "package": ["NumPy", "Pandas", "Polars", "Great Tables", "Pointblank"],\n'
            '    "description": [\n'
            '        "Fundamental package for scientific computing with Python. Provides N-dimensional arrays, linear algebra, Fourier transforms, and random number generation.",\n'
            '        "Powerful data structures for data analysis, time series, and statistics. Built on NumPy with labeled axes, automatic alignment, and rich I/O.",\n'
            '        "Lightning-fast DataFrame library in Rust with a Python API. Lazy evaluation, multi-threaded queries, and Apache Arrow memory format.",\n'
            '        "Build beautiful, publication-quality tables in Python. Supports Polars and Pandas DataFrames with fine-grained styling, formatting, and export.",\n'
            '        "Data validation library for Python. Define expectations, validate data, and generate detailed reports with table-level and column-level checks.",\n'
            "    ],\n"
            '    "version": ["1.26.0", "2.2.0", "0.20.0", "0.15.0", "0.14.0"],\n'
            "}\n"
            "\n"
            "tbl_preview(data, show_all=True)\n"
            "```\n"
            "\n"
            "## Narrow Max Width (120px)\n"
            "\n"
            "Force aggressive truncation with a tight `max_col_width`:\n"
            "\n"
            "```{python}\n"
            "tbl_preview(data, show_all=True, max_col_width=120)\n"
            "```\n"
            "\n"
            "## Wide Max Width (500px)\n"
            "\n"
            "Allow generous room — long text is still capped, but more is visible:\n"
            "\n"
            "```{python}\n"
            "tbl_preview(data, show_all=True, max_col_width=500)\n"
            "```\n"
            "\n"
            "## Mixed Short and Long Columns\n"
            "\n"
            "Short numeric/code columns alongside verbose text — each column\n"
            "gets its own computed width.\n"
            "\n"
            "```{python}\n"
            "data = {\n"
            '    "code": ["E001", "E002", "E003", "W001", "W002", "I001", "I002", "E004"],\n'
            '    "severity": ["error", "error", "error", "warning", "warning", "info", "info", "error"],\n'
            '    "message": [\n'
            '        "Undefined variable: foobar",\n'
            '        "Type mismatch: expected int, got str in argument `count` of function process_batch()",\n'
            '        "Division by zero in expression total / n_items where n_items evaluates to 0",\n'
            '        "Unused import: os (imported but never referenced in module)",\n'
            '        "Variable `tmp` assigned on line 42 but never used anywhere in the function body",\n'
            '        "Module docstring missing: consider adding a module-level docstring",\n'
            '        "Line too long: 127 characters (max 120). Consider breaking this into multiple lines for readability",\n'
            '        "Syntax error: unexpected token ) at position 34 in expression parse(input))",\n'
            "    ],\n"
            '    "line": [12, 45, 78, 3, 42, 1, 99, 34],\n'
            "}\n"
            "\n"
            "tbl_preview(data, show_all=True)\n"
            "```\n"
        ),
        # ── File-format pages ─────────────────────────────────────────────
        "user_guide/08-tsv-files.qmd": (
            "---\n"
            "title: TSV Files\n"
            "---\n"
            "\n"
            "## Read a TSV File\n"
            "\n"
            "`tbl_preview()` auto-detects `.tsv` and `.tab` files and reads\n"
            "them with tab-delimited parsing.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import pathlib\n"
            "\n"
            "tsv_path = pathlib.Path('assets/cities.tsv')\n"
            "tsv_path.parent.mkdir(parents=True, exist_ok=True)\n"
            "tsv_path.write_text(\n"
            "    'city\\tcountry\\tpopulation\\tarea_km2\\n'\n"
            "    'Tokyo\\tJapan\\t13960000\\t2194\\n'\n"
            "    'Delhi\\tIndia\\t11030000\\t1484\\n'\n"
            "    'Shanghai\\tChina\\t24870000\\t6341\\n'\n"
            "    'São Paulo\\tBrazil\\t12330000\\t1521\\n'\n"
            "    'Mexico City\\tMexico\\t9210000\\t1485\\n'\n"
            "    'Cairo\\tEgypt\\t9540000\\t3085\\n'\n"
            "    'Mumbai\\tIndia\\t12440000\\t603\\n'\n"
            "    'Beijing\\tChina\\t21540000\\t16411\\n'\n"
            ")\n"
            "```\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "tbl_preview('assets/cities.tsv', show_all=True)\n"
            "```\n"
            "\n"
            "The badge shows **TSV** and the header reports the correct\n"
            "row and column counts.\n"
        ),
        "user_guide/09-jsonl-files.qmd": (
            "---\n"
            "title: JSONL Files\n"
            "---\n"
            "\n"
            "## Read a JSONL File\n"
            "\n"
            "Newline-delimited JSON (`.jsonl` / `.ndjson`) is a common\n"
            "format for streaming data and log records.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import pathlib, json\n"
            "\n"
            "records = [\n"
            "    {'timestamp': '2025-01-15T08:30:00', 'level': 'INFO', 'module': 'auth', 'message': 'User login successful'},\n"
            "    {'timestamp': '2025-01-15T08:31:12', 'level': 'WARNING', 'module': 'db', 'message': 'Slow query detected (3.2s)'},\n"
            "    {'timestamp': '2025-01-15T08:32:45', 'level': 'ERROR', 'module': 'api', 'message': 'Request timeout on /v2/users'},\n"
            "    {'timestamp': '2025-01-15T08:33:01', 'level': 'INFO', 'module': 'cache', 'message': 'Cache miss for key user:42'},\n"
            "    {'timestamp': '2025-01-15T08:34:20', 'level': 'DEBUG', 'module': 'auth', 'message': 'Token refresh for session abc123'},\n"
            "    {'timestamp': '2025-01-15T08:35:55', 'level': 'ERROR', 'module': 'db', 'message': 'Connection pool exhausted'},\n"
            "    {'timestamp': '2025-01-15T08:36:10', 'level': 'INFO', 'module': 'api', 'message': 'Health check passed'},\n"
            "    {'timestamp': '2025-01-15T08:37:30', 'level': 'WARNING', 'module': 'auth', 'message': 'Failed login attempt from 192.168.1.100'},\n"
            "]\n"
            "\n"
            "jsonl_path = pathlib.Path('assets/server_logs.jsonl')\n"
            "jsonl_path.parent.mkdir(parents=True, exist_ok=True)\n"
            "jsonl_path.write_text('\\n'.join(json.dumps(r) for r in records) + '\\n')\n"
            "```\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "tbl_preview('assets/server_logs.jsonl', show_all=True)\n"
            "```\n"
            "\n"
            "## NDJSON Extension\n"
            "\n"
            "The `.ndjson` extension is treated identically:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import shutil\n"
            "shutil.copy('assets/server_logs.jsonl', 'assets/server_logs.ndjson')\n"
            "```\n"
            "\n"
            "```{python}\n"
            "tbl_preview('assets/server_logs.ndjson', show_all=True)\n"
            "```\n"
        ),
        "user_guide/10-parquet-files.qmd": (
            "---\n"
            "title: Parquet Files\n"
            "---\n"
            "\n"
            "## Read a Parquet File\n"
            "\n"
            "Apache Parquet is a columnar storage format popular in data\n"
            "engineering workflows.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import polars as pl, pathlib\n"
            "\n"
            "df = pl.DataFrame({\n"
            "    'product': ['Widget', 'Gadget', 'Gizmo', 'Doohickey', 'Thingamajig'],\n"
            "    'category': ['Electronics', 'Tools', 'Kitchen', 'Garden', 'Office'],\n"
            "    'price': [29.99, 49.50, 12.00, 8.75, 199.99],\n"
            "    'in_stock': [True, False, True, True, False],\n"
            "    'rating': [4.5, 3.8, 4.9, 4.2, 2.1],\n"
            "})\n"
            "\n"
            "pq_path = pathlib.Path('assets/products.parquet')\n"
            "pq_path.parent.mkdir(parents=True, exist_ok=True)\n"
            "df.write_parquet(str(pq_path))\n"
            "```\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "tbl_preview('assets/products.parquet', show_all=True)\n"
            "```\n"
            "\n"
            "The badge shows **Parquet** and dtype labels are preserved\n"
            "from the original Polars schema.\n"
        ),
        "user_guide/11-feather-arrow-files.qmd": (
            "---\n"
            "title: Feather & Arrow IPC Files\n"
            "---\n"
            "\n"
            "## Feather File\n"
            "\n"
            "Feather (Apache Arrow IPC format) is fast for local analytics.\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import polars as pl, pathlib\n"
            "\n"
            "df = pl.DataFrame({\n"
            "    'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank'],\n"
            "    'department': ['Engineering', 'Marketing', 'Engineering', 'Sales', 'Marketing', 'Sales'],\n"
            "    'salary': [95000, 72000, 105000, 68000, 88000, 71000],\n"
            "    'years': [5, 3, 8, 2, 6, 4],\n"
            "})\n"
            "\n"
            "feather_path = pathlib.Path('assets/employees.feather')\n"
            "feather_path.parent.mkdir(parents=True, exist_ok=True)\n"
            "df.write_ipc(str(feather_path))\n"
            "```\n"
            "\n"
            "```{python}\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "tbl_preview('assets/employees.feather', show_all=True)\n"
            "```\n"
            "\n"
            "## Arrow IPC Extension\n"
            "\n"
            "Files with `.arrow` or `.ipc` extensions are also read as\n"
            "Arrow IPC, but get the **Arrow** badge instead of Feather:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "import shutil\n"
            "shutil.copy('assets/employees.feather', 'assets/employees.arrow')\n"
            "```\n"
            "\n"
            "```{python}\n"
            "tbl_preview('assets/employees.arrow', show_all=True)\n"
            "```\n"
        ),
        "user_guide/12-arrow-tables.qmd": (
            "---\n"
            "title: PyArrow Tables\n"
            "---\n"
            "\n"
            "## In-Memory Arrow Table\n"
            "\n"
            "`tbl_preview()` also accepts a `pyarrow.Table` directly —\n"
            "no file needed.\n"
            "\n"
            "```{python}\n"
            "import pyarrow as pa\n"
            "from great_docs import tbl_preview\n"
            "\n"
            "tbl = pa.table({\n"
            "    'city': ['Tokyo', 'Delhi', 'Shanghai', 'São Paulo', 'Mexico City',\n"
            "             'Cairo', 'Mumbai', 'Beijing', 'Dhaka', 'Osaka'],\n"
            "    'country': ['Japan', 'India', 'China', 'Brazil', 'Mexico',\n"
            "                'Egypt', 'India', 'China', 'Bangladesh', 'Japan'],\n"
            "    'population_m': [13.96, 11.03, 24.87, 12.33, 9.21,\n"
            "                     9.54, 12.44, 21.54, 8.91, 2.75],\n"
            "    'area_km2': [2194, 1484, 6341, 1521, 1485,\n"
            "                 3085, 603, 16411, 306, 225],\n"
            "})\n"
            "\n"
            "tbl_preview(tbl, show_all=True)\n"
            "```\n"
            "\n"
            "## Arrow Table with Typed Columns\n"
            "\n"
            "PyArrow preserves rich type information — booleans, dates,\n"
            "decimals — which `tbl_preview()` maps to short dtype labels.\n"
            "\n"
            "```{python}\n"
            "import pyarrow as pa\n"
            "from datetime import date\n"
            "\n"
            "tbl = pa.table({\n"
            "    'event': ['Launch', 'Update', 'Hotfix', 'Deprecation'],\n"
            "    'date': [date(2025, 1, 15), date(2025, 3, 1), date(2025, 3, 12), date(2025, 6, 30)],\n"
            "    'critical': [True, False, True, False],\n"
            "    'affected_users': [50000, 12000, 8500, 2000],\n"
            "})\n"
            "\n"
            "tbl_preview(tbl, show_all=True)\n"
            "```\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-tbl-preview",
        "detected_module": "gdtest_tbl_preview",
        "detected_parser": "numpy",
        "export_names": [
            "sample_scores",
            "sample_inventory",
            "sample_wide",
            "sample_missing",
            "sample_types",
        ],
        "num_exports": 5,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
