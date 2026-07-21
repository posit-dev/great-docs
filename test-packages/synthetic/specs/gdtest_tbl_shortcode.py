"""
gdtest_tbl_shortcode — Exercise the {{< tbl-preview >}} Quarto shortcode.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7
Focus: The tbl-preview shortcode with data files in assets/ — CSV, TSV,
       JSONL — exercising every shortcode parameter. No Python code cells;
       all table rendering is done purely through the shortcode.

       1. CSV basics — default shortcode, caption, column subset.
       2. TSV files — tab-delimited data via the shortcode.
       3. JSONL files — newline-delimited JSON via the shortcode.
       4. Shortcode options — head/tail, show_all, hide row numbers,
          hide dtypes, hide dimensions, max_col_width.
       5. Multiple tables — several shortcodes on a single page.
"""

SPEC = {
    "name": "gdtest_tbl_shortcode",
    "description": "tbl-preview Quarto shortcode with CSV, TSV, and JSONL data files.",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-tbl-shortcode",
            "version": "0.1.0",
            "description": "Showcase for the tbl-preview Quarto shortcode",
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
            "# gdtest-tbl-shortcode\n\n"
            "A showcase site demonstrating the `{{< tbl-preview >}}` Quarto\n"
            "shortcode. All tables are rendered from data files in `assets/`\n"
            "— no Python code cells needed.\n"
        ),
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_tbl_shortcode/__init__.py": (
            '"""Shortcode demo package."""\n'
            "\n"
            '__version__ = "0.1.0"\n'
            '__all__ = ["describe"]\n'
            "\n"
            "\n"
            "def describe(name: str) -> str:\n"
            '    """Describe a dataset by name.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    name\n"
            "        The dataset name.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        A human-readable description.\n"
            '    """\n'
            '    return f"Dataset: {name}"\n'
        ),
        # ── Data files in assets/ ─────────────────────────────────────────
        "assets/students.csv": (
            "name,subject,score,grade,passed\n"
            "Alice,Math,95.5,A,true\n"
            "Bob,Science,82.0,B,true\n"
            "Charlie,English,71.3,C,true\n"
            "Diana,History,60.0,D,true\n"
            "Eve,Art,55.8,F,false\n"
            "Frank,Math,88.2,B+,true\n"
            "Grace,Science,79.9,C+,true\n"
            "Hank,English,91.0,A-,true\n"
            "Iris,History,66.4,D+,true\n"
            "Jack,Art,73.7,C,true\n"
        ),
        "assets/products.tsv": (
            "product\tcategory\tprice\tstock\trating\n"
            "Widget\tElectronics\t29.99\t150\t4.5\n"
            "Gadget\tTools\t49.50\t80\t3.8\n"
            "Gizmo\tKitchen\t12.00\t300\t4.9\n"
            "Doohickey\tGarden\t8.75\t0\t4.2\n"
            "Thingamajig\tOffice\t199.99\t25\t2.1\n"
            "Contraption\tElectronics\t65.00\t44\t3.5\n"
            "Apparatus\tTools\t120.00\t12\t4.7\n"
        ),
        "assets/server_logs.jsonl": (
            '{"timestamp":"2025-01-15T08:30:00","level":"INFO","module":"auth","message":"User login successful"}\n'
            '{"timestamp":"2025-01-15T08:31:12","level":"WARNING","module":"db","message":"Slow query detected (3.2s)"}\n'
            '{"timestamp":"2025-01-15T08:32:45","level":"ERROR","module":"api","message":"Request timeout on /v2/users"}\n'
            '{"timestamp":"2025-01-15T08:33:01","level":"INFO","module":"cache","message":"Cache miss for key user:42"}\n'
            '{"timestamp":"2025-01-15T08:34:20","level":"DEBUG","module":"auth","message":"Token refresh for session abc123"}\n'
            '{"timestamp":"2025-01-15T08:35:55","level":"ERROR","module":"db","message":"Connection pool exhausted"}\n'
        ),
        "assets/wide_metrics.csv": (
            "metric,jan,feb,mar,apr,may,jun,jul,aug,sep,oct,nov,dec\n"
            "revenue,120.5,135.2,128.7,142.3,155.8,148.9,162.1,170.4,165.3,178.2,185.6,192.0\n"
            "costs,80.1,82.3,79.5,85.2,90.1,88.7,95.3,100.2,97.8,105.1,110.3,115.0\n"
            "users,1200,1350,1280,1420,1558,1489,1621,1704,1653,1782,1856,1920\n"
            "sessions,3500,3800,3600,4100,4500,4200,4800,5100,4900,5300,5600,5800\n"
            "conversion,3.2,3.5,3.1,3.8,4.0,3.7,4.2,4.5,4.3,4.6,4.8,5.0\n"
        ),
        # ── User guide pages (flat layout) ────────────────────────────────
        "user_guide/01-csv-basics.qmd": (
            "---\n"
            "title: CSV via Shortcode\n"
            "---\n"
            "\n"
            "## Default Preview\n"
            "\n"
            "The simplest usage — just point at a CSV file:\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" >}}\n'
            "\n"
            "## With Caption\n"
            "\n"
            "Add a descriptive caption:\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" caption="Student Scores — Fall 2025" >}}\n'
            "\n"
            "## Column Subset\n"
            "\n"
            "Show only selected columns:\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" columns="name,score,grade" show_all="true" >}}\n'
        ),
        "user_guide/02-tsv-files.qmd": (
            "---\n"
            "title: TSV via Shortcode\n"
            "---\n"
            "\n"
            "## Product Inventory\n"
            "\n"
            "Tab-delimited files work just the same:\n"
            "\n"
            '{{< tbl-preview file="assets/products.tsv" show_all="true" >}}\n'
            "\n"
            "## Head Only\n"
            "\n"
            "Show just the first 3 rows:\n"
            "\n"
            '{{< tbl-preview file="assets/products.tsv" n_head="3" n_tail="0" >}}\n'
        ),
        "user_guide/03-jsonl-files.qmd": (
            "---\n"
            "title: JSONL via Shortcode\n"
            "---\n"
            "\n"
            "## Server Logs\n"
            "\n"
            "JSONL (newline-delimited JSON) files are auto-detected:\n"
            "\n"
            '{{< tbl-preview file="assets/server_logs.jsonl" show_all="true" >}}\n'
            "\n"
            "## With Narrow Columns\n"
            "\n"
            "Constrain column widths to see truncation:\n"
            "\n"
            '{{< tbl-preview file="assets/server_logs.jsonl" show_all="true" max_col_width="120" >}}\n'
        ),
        "user_guide/04-shortcode-options.qmd": (
            "---\n"
            "title: Shortcode Options\n"
            "---\n"
            "\n"
            "## Show All Rows\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" show_all="true" >}}\n'
            "\n"
            "## Custom Head/Tail Split\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" n_head="3" n_tail="2" >}}\n'
            "\n"
            "## Hide Row Numbers\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" show_all="true" show_row_numbers="false" >}}\n'
            "\n"
            "## Hide Dtype Labels\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" show_all="true" show_dtypes="false" >}}\n'
            "\n"
            "## Hide Dimensions Banner\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" show_all="true" show_dimensions="false" >}}\n'
            "\n"
            "## Minimal Chrome\n"
            "\n"
            "No row numbers, no dtypes, no dimensions — just the data:\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" show_all="true" '
            'show_row_numbers="false" show_dtypes="false" show_dimensions="false" >}}\n'
        ),
        "user_guide/05-multiple-tables.qmd": (
            "---\n"
            "title: Multiple Tables\n"
            "---\n"
            "\n"
            "## Side-by-Side Comparisons\n"
            "\n"
            "Multiple shortcodes on one page, each with different files:\n"
            "\n"
            "### Students (CSV)\n"
            "\n"
            '{{< tbl-preview file="assets/students.csv" n_head="3" n_tail="0" caption="Top 3 Students" >}}\n'
            "\n"
            "### Products (TSV)\n"
            "\n"
            '{{< tbl-preview file="assets/products.tsv" n_head="3" n_tail="0" caption="Top 3 Products" >}}\n'
            "\n"
            "### Server Logs (JSONL)\n"
            "\n"
            '{{< tbl-preview file="assets/server_logs.jsonl" n_head="3" n_tail="0" caption="Recent Logs" >}}\n'
            "\n"
            "## Wide Table\n"
            "\n"
            "A 13-column metrics table with horizontal scroll:\n"
            "\n"
            '{{< tbl-preview file="assets/wide_metrics.csv" show_all="true" caption="Monthly Metrics 2025" >}}\n'
        ),
    },
    "expected": {
        "detected_name": "gdtest-tbl-shortcode",
        "detected_module": "gdtest_tbl_shortcode",
        "detected_parser": "numpy",
        "export_names": ["describe"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
