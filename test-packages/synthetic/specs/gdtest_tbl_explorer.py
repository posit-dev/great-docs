"""
gdtest_tbl_explorer — Interactive table explorer showcase.

Dimensions: A1, B1, C1, D1, M4, G1
Focus: Exercises the ``tbl_explorer()`` function with many different table
       shapes, data types, display options, and interactive feature toggles.
       The user guide has eight pages:

       1. Basic explorer — dict data, default options, sorting & filtering.
       2. Large table — 200-row dataset, pagination, page navigation.
       3. Column toggling — wide table, hide/show columns, column subsets.
       4. Copy & download — copy to clipboard, CSV download.
       5. Missing values — None/NaN highlighting, mixed types.
       6. Minimal chrome — hide row numbers, dtypes, dimensions.
       7. Shortcode explorer — exercise the {{< tbl-explorer >}} shortcode.
       8. Side-by-side — tbl_preview() vs tbl_explorer() comparison.

       The API reference documents helper functions that generate sample
       data for the explorer demos.
"""

SPEC = {
    "name": "gdtest_tbl_explorer",
    "description": "Interactive table explorer showcase with sorting, filtering, pagination.",
    "dimensions": ["A1", "B1", "C1", "D1", "M2", "G1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-tbl-explorer",
            "version": "0.1.0",
            "description": "Showcase for the tbl_explorer() interactive table feature",
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
            "# gdtest-tbl-explorer\n\n"
            "A showcase site demonstrating the `tbl_explorer()` function from\n"
            "Great Docs. Each user-guide page exercises a different combination\n"
            "of data sources, interactive features, and display options.\n"
        ),
        # ── Package source ────────────────────────────────────────────────
        "gdtest_tbl_explorer/__init__.py": '''\
            """Sample data generators for table explorer demos."""

            __version__ = "0.1.0"
            __all__ = [
                "sample_cities",
                "sample_products",
                "sample_wide",
                "sample_missing",
                "sample_large",
            ]

            from .data import (
                sample_cities,
                sample_products,
                sample_wide,
                sample_missing,
                sample_large,
            )
        ''',
        "gdtest_tbl_explorer/data.py": '''\
            """Functions that generate sample data for explorer demos."""

            from __future__ import annotations


            def sample_cities(n: int = 12) -> dict[str, list]:
                """
                Generate a world cities dataset.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with city, country, population,
                    latitude, and longitude columns.

                Examples
                --------
                >>> data = sample_cities(5)
                >>> len(data["city"])
                5
                """
                cities = [
                    ("Tokyo", "Japan", 13960000, 35.6762, 139.6503),
                    ("Paris", "France", 2161000, 48.8566, 2.3522),
                    ("New York", "USA", 8336000, 40.7128, -74.0060),
                    ("London", "UK", 8982000, 51.5074, -0.1278),
                    ("Sydney", "Australia", 5312000, -33.8688, 151.2093),
                    ("Berlin", "Germany", 3645000, 52.5200, 13.4050),
                    ("Mumbai", "India", 20411000, 19.0760, 72.8777),
                    ("São Paulo", "Brazil", 12330000, -23.5505, -46.6333),
                    ("Cairo", "Egypt", 10230000, 30.0444, 31.2357),
                    ("Toronto", "Canada", 2930000, 43.6532, -79.3832),
                    ("Seoul", "South Korea", 9776000, 37.5665, 126.9780),
                    ("Mexico City", "Mexico", 9210000, 19.4326, -99.1332),
                    ("Lagos", "Nigeria", 15400000, 6.5244, 3.3792),
                    ("Bangkok", "Thailand", 10540000, 13.7563, 100.5018),
                    ("Istanbul", "Turkey", 15460000, 41.0082, 28.9784),
                ]
                rows = cities[:n]
                return {
                    "city": [r[0] for r in rows],
                    "country": [r[1] for r in rows],
                    "population": [r[2] for r in rows],
                    "latitude": [r[3] for r in rows],
                    "longitude": [r[4] for r in rows],
                }


            def sample_products(n: int = 15) -> dict[str, list]:
                """
                Generate a product catalog dataset.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with product, category, price,
                    stock, rating, and in_stock columns.

                Examples
                --------
                >>> data = sample_products(5)
                >>> len(data["product"])
                5
                """
                import random
                random.seed(42)
                products = [
                    "Widget", "Gadget", "Doohickey", "Thingamajig",
                    "Gizmo", "Whatchamacallit", "Contraption", "Apparatus",
                    "Device", "Instrument", "Mechanism", "Implement",
                    "Tool", "Utensil", "Component",
                ]
                categories = ["Electronics", "Tools", "Kitchen", "Garden", "Office"]
                rows = []
                for i in range(n):
                    name = products[i % len(products)]
                    cat = random.choice(categories)
                    price = round(random.uniform(5.0, 250.0), 2)
                    stock = random.randint(0, 500)
                    rating = round(random.uniform(1.0, 5.0), 1)
                    rows.append((name, cat, price, stock, rating, stock > 0))
                return {
                    "product": [r[0] for r in rows],
                    "category": [r[1] for r in rows],
                    "price": [r[2] for r in rows],
                    "stock": [r[3] for r in rows],
                    "rating": [r[4] for r in rows],
                    "in_stock": [r[5] for r in rows],
                }


            def sample_wide(n_rows: int = 10, n_cols: int = 15) -> dict[str, list]:
                """
                Generate a wide dataset with many numeric columns.

                Parameters
                ----------
                n_rows
                    Number of rows.
                n_cols
                    Number of data columns (plus an id column).

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with an ``id`` column and
                    ``metric_001`` through ``metric_{n_cols:03d}``.

                Examples
                --------
                >>> data = sample_wide(5, 8)
                >>> len(data)
                9
                """
                import random
                random.seed(7)
                result = {"id": list(range(n_rows))}
                for i in range(n_cols):
                    result[f"metric_{i+1:03d}"] = [
                        round(random.gauss(0, 1), 3) for _ in range(n_rows)
                    ]
                return result


            def sample_missing(n: int = 12) -> dict[str, list]:
                """
                Generate a dataset with scattered missing values.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with name, value, category, and
                    score columns. Some cells are None.

                Examples
                --------
                >>> data = sample_missing(5)
                >>> None in data["value"]
                True
                """
                import random
                random.seed(13)
                names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon",
                         "Zeta", "Eta", "Theta", "Iota", "Kappa",
                         "Lambda", "Mu"]
                categories = ["A", "B", "C", None]
                rows_name = [names[i % len(names)] for i in range(n)]
                rows_val = [
                    None if random.random() < 0.25
                    else round(random.uniform(10, 100), 1)
                    for _ in range(n)
                ]
                rows_cat = [random.choice(categories) for _ in range(n)]
                rows_score = [
                    None if random.random() < 0.2
                    else random.randint(1, 100)
                    for _ in range(n)
                ]
                return {
                    "name": rows_name,
                    "value": rows_val,
                    "category": rows_cat,
                    "score": rows_score,
                }


            def sample_large(n: int = 200) -> dict[str, list]:
                """
                Generate a large dataset for pagination testing.

                Parameters
                ----------
                n
                    Number of rows.

                Returns
                -------
                dict[str, list]
                    Column-oriented dict with id, name, department, salary,
                    years, and active columns.

                Examples
                --------
                >>> data = sample_large(50)
                >>> len(data["id"])
                50
                """
                import random
                random.seed(123)
                first_names = [
                    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank",
                    "Grace", "Hank", "Iris", "Jack", "Karen", "Leo",
                    "Mona", "Nate", "Olivia", "Paul", "Quinn", "Rosa",
                ]
                depts = [
                    "Engineering", "Marketing", "Sales", "Finance",
                    "HR", "Operations", "Legal", "R&D",
                ]
                return {
                    "id": list(range(1, n + 1)),
                    "name": [random.choice(first_names) for _ in range(n)],
                    "department": [random.choice(depts) for _ in range(n)],
                    "salary": [random.randint(50000, 200000) for _ in range(n)],
                    "years": [random.randint(1, 30) for _ in range(n)],
                    "active": [random.random() > 0.15 for _ in range(n)],
                }
        ''',
        # ── Data files for shortcode demos ────────────────────────────────
        "docs/assets/cities.csv": (
            "city,country,population,latitude,longitude\n"
            "Tokyo,Japan,13960000,35.6762,139.6503\n"
            "Paris,France,2161000,48.8566,2.3522\n"
            "New York,USA,8336000,40.7128,-74.0060\n"
            "London,UK,8982000,51.5074,-0.1278\n"
            "Sydney,Australia,5312000,-33.8688,151.2093\n"
            "Berlin,Germany,3645000,52.5200,13.4050\n"
            "Mumbai,India,20411000,19.0760,72.8777\n"
            "São Paulo,Brazil,12330000,-23.5505,-46.6333\n"
            "Cairo,Egypt,10230000,30.0444,31.2357\n"
            "Toronto,Canada,2930000,43.6532,-79.3832\n"
            "Seoul,South Korea,9776000,37.5665,126.9780\n"
            "Mexico City,Mexico,9210000,19.4326,-99.1332\n"
        ),
        "docs/assets/products.tsv": (
            "product\tcategory\tprice\tstock\trating\n"
            "Widget\tElectronics\t29.99\t150\t4.5\n"
            "Gadget\tTools\t49.50\t80\t3.8\n"
            "Gizmo\tKitchen\t12.00\t300\t4.9\n"
            "Doohickey\tGarden\t8.75\t0\t4.2\n"
            "Thingamajig\tOffice\t199.99\t25\t2.1\n"
            "Contraption\tElectronics\t65.00\t44\t3.5\n"
            "Apparatus\tTools\t120.00\t12\t4.7\n"
        ),
        "docs/assets/logs.jsonl": (
            '{"ts":"2025-01-15T08:30:00","level":"INFO","module":"auth","msg":"User login OK"}\n'
            '{"ts":"2025-01-15T08:31:12","level":"WARN","module":"db","msg":"Slow query (3.2s)"}\n'
            '{"ts":"2025-01-15T08:32:45","level":"ERROR","module":"api","msg":"Timeout /v2/users"}\n'
            '{"ts":"2025-01-15T08:33:01","level":"INFO","module":"cache","msg":"Cache miss user:42"}\n'
            '{"ts":"2025-01-15T08:34:20","level":"DEBUG","module":"auth","msg":"Token refresh abc123"}\n'
            '{"ts":"2025-01-15T08:35:55","level":"ERROR","module":"db","msg":"Pool exhausted"}\n'
        ),
        # ── User guide pages ──────────────────────────────────────────────
        "docs/user_guide/01-basic-explorer.qmd": (
            "---\n"
            "title: Basic Explorer\n"
            "---\n"
            "\n"
            "The `tbl_explorer()` function creates interactive tables with\n"
            "sorting, filtering, pagination, and more.\n"
            "\n"
            "## Default Options\n"
            "\n"
            "Pass a dictionary and get a fully interactive table:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "from gdtest_tbl_explorer import sample_cities\n"
            "\n"
            "tbl_explorer(sample_cities())\n"
            "```\n"
            "\n"
            "Try clicking column headers to sort, or type in the filter box.\n"
            "\n"
            "## With Caption\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            'tbl_explorer(sample_cities(), caption="World Cities")\n'
            "```\n"
            "\n"
            "## Product Catalog\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_tbl_explorer import sample_products\n"
            "\n"
            'tbl_explorer(sample_products(), caption="Product Catalog")\n'
            "```\n"
        ),
        "docs/user_guide/02-pagination.qmd": (
            "---\n"
            "title: Pagination\n"
            "---\n"
            "\n"
            "With larger datasets, `tbl_explorer()` paginates automatically.\n"
            "\n"
            "## Default Page Size (20 rows)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "from gdtest_tbl_explorer import sample_large\n"
            "\n"
            'tbl_explorer(sample_large(200), caption="200 Employees")\n'
            "```\n"
            "\n"
            "## Custom Page Size (10 rows)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            'tbl_explorer(sample_large(200), page_size=10, caption="10 per page")\n'
            "```\n"
            "\n"
            "## Large Page Size (50 rows)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            'tbl_explorer(sample_large(200), page_size=50, caption="50 per page")\n'
            "```\n"
            "\n"
            "## No Pagination\n"
            "\n"
            "Set `page_size=0` to show all rows at once:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            'tbl_explorer(sample_large(30), page_size=0, caption="All 30 rows")\n'
            "```\n"
        ),
        "docs/user_guide/03-column-toggle.qmd": (
            "---\n"
            "title: Column Toggling\n"
            "---\n"
            "\n"
            "Use the **Columns** dropdown in the toolbar to show/hide columns.\n"
            "\n"
            "## Wide Table\n"
            "\n"
            "This table has 16 columns — try hiding some:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "from gdtest_tbl_explorer import sample_wide\n"
            "\n"
            'tbl_explorer(sample_wide(10, 15), caption="Wide Metrics Table")\n'
            "```\n"
            "\n"
            "## Column Subset\n"
            "\n"
            "Pre-select specific columns with `columns=`:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from gdtest_tbl_explorer import sample_cities\n"
            "\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            '    columns=["city", "country", "population"],\n'
            '    caption="Cities — 3 columns only",\n'
            ")\n"
            "```\n"
            "\n"
            "## Toggle Disabled\n"
            "\n"
            "Set `column_toggle=False` to remove the dropdown:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            "    column_toggle=False,\n"
            '    caption="No column toggle",\n'
            ")\n"
            "```\n"
        ),
        "docs/user_guide/04-copy-download.qmd": (
            "---\n"
            "title: Copy & Download\n"
            "---\n"
            "\n"
            "The toolbar includes **Copy** (TSV to clipboard) and **Download**\n"
            "(CSV file) buttons.\n"
            "\n"
            "## Full Controls\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "from gdtest_tbl_explorer import sample_products\n"
            "\n"
            'tbl_explorer(sample_products(), caption="Copy or download this table")\n'
            "```\n"
            "\n"
            "## Copy Only (No Download)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_products(),\n"
            "    downloadable=False,\n"
            '    caption="Copy button only",\n'
            ")\n"
            "```\n"
            "\n"
            "## Download Only (No Copy)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_products(),\n"
            "    copyable=False,\n"
            '    caption="Download button only",\n'
            ")\n"
            "```\n"
            "\n"
            "## No Export Controls\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_products(),\n"
            "    copyable=False,\n"
            "    downloadable=False,\n"
            '    caption="No export buttons",\n'
            ")\n"
            "```\n"
        ),
        "docs/user_guide/05-missing-values.qmd": (
            "---\n"
            "title: Missing Values\n"
            "---\n"
            "\n"
            "Missing values (`None`, `NaN`) are highlighted in red by default.\n"
            "\n"
            "## Default Highlighting\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "from gdtest_tbl_explorer import sample_missing\n"
            "\n"
            'tbl_explorer(sample_missing(), caption="Missing values highlighted")\n'
            "```\n"
            "\n"
            "## Highlighting Off\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_missing(),\n"
            "    highlight_missing=False,\n"
            '    caption="Missing values NOT highlighted",\n'
            ")\n"
            "```\n"
        ),
        "docs/user_guide/06-minimal-chrome.qmd": (
            "---\n"
            "title: Minimal Chrome\n"
            "---\n"
            "\n"
            "Strip away table chrome for a clean, data-focused look.\n"
            "\n"
            "## No Row Numbers\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "from gdtest_tbl_explorer import sample_cities\n"
            "\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            "    show_row_numbers=False,\n"
            '    caption="No row numbers",\n'
            ")\n"
            "```\n"
            "\n"
            "## No Dtype Labels\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            "    show_dtypes=False,\n"
            '    caption="No dtype labels",\n'
            ")\n"
            "```\n"
            "\n"
            "## No Header Banner\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            "    show_dimensions=False,\n"
            '    caption="No header banner",\n'
            ")\n"
            "```\n"
            "\n"
            "## Fully Minimal\n"
            "\n"
            "No row numbers, no dtypes, no dimensions — just the data and controls:\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            "    show_row_numbers=False,\n"
            "    show_dtypes=False,\n"
            "    show_dimensions=False,\n"
            '    caption="Fully minimal",\n'
            ")\n"
            "```\n"
            "\n"
            "## Filter Only (No Other Controls)\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "tbl_explorer(\n"
            "    sample_cities(),\n"
            "    sortable=False,\n"
            "    column_toggle=False,\n"
            "    copyable=False,\n"
            "    downloadable=False,\n"
            '    caption="Filter only",\n'
            ")\n"
            "```\n"
        ),
        "docs/user_guide/07-shortcode.qmd": (
            "---\n"
            "title: Shortcode Explorer\n"
            "---\n"
            "\n"
            "The `{{< tbl-explorer >}}` shortcode embeds interactive tables\n"
            "from data files — no Python code cells needed.\n"
            "\n"
            "## CSV File\n"
            "\n"
            '{{< tbl-explorer file="assets/cities.csv" >}}\n'
            "\n"
            "## With Caption\n"
            "\n"
            '{{< tbl-explorer file="assets/cities.csv" caption="World Cities (shortcode)" >}}\n'
            "\n"
            "## TSV File\n"
            "\n"
            '{{< tbl-explorer file="assets/products.tsv" caption="Products (TSV)" >}}\n'
            "\n"
            "## JSONL File\n"
            "\n"
            '{{< tbl-explorer file="assets/logs.jsonl" caption="Server Logs (JSONL)" >}}\n'
            "\n"
            "## Custom Options\n"
            "\n"
            '{{< tbl-explorer file="assets/cities.csv" page_size="5" '
            'caption="5 per page" >}}\n'
            "\n"
            "## No Filter\n"
            "\n"
            '{{< tbl-explorer file="assets/cities.csv" filterable="false" '
            'caption="No filter input" >}}\n'
        ),
        "docs/user_guide/08-comparison.qmd": (
            "---\n"
            "title: Preview vs Explorer\n"
            "---\n"
            "\n"
            "Compare the static `tbl_preview()` with the interactive\n"
            "`tbl_explorer()` side by side.\n"
            "\n"
            "## Static Preview\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_preview\n"
            "from gdtest_tbl_explorer import sample_cities\n"
            "\n"
            'tbl_preview(sample_cities(), caption="Static preview")\n'
            "```\n"
            "\n"
            "## Interactive Explorer\n"
            "\n"
            "```{python}\n"
            "#| echo: false\n"
            "from great_docs import tbl_explorer\n"
            "\n"
            'tbl_explorer(sample_cities(), caption="Interactive explorer")\n'
            "```\n"
            "\n"
            "The explorer adds a toolbar with filter, column toggle, copy,\n"
            "download, and reset controls. Column headers are sortable.\n"
            "The static preview is lighter and works without JavaScript.\n"
        ),
    },
}
