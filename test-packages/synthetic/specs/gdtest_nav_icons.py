"""
gdtest_nav_icons — Showcase navigation icons on navbar and sidebar.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7, K53, N2
Focus: nav_icons config with Lucide icons on navbar labels and sidebar
       section headers for visual identification. Includes a custom
       Tutorials section to test incomplete icon coverage and section
       header icons beyond the User Guide.
"""

SPEC = {
    "name": "gdtest_nav_icons",
    "description": "Navigation icons on navbar and sidebar entries",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7", "K53", "N2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-nav-icons",
            "version": "1.0.0",
            "description": "A data-analysis toolkit with Lucide navigation icons",
            "urls": {
                "Homepage": "https://example.com/nav-icons",
                "Repository": "https://github.com/example/nav-icons",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "NavIcons Demo",
        "parser": "google",
        "navbar_style": "sky",
        "announcement": {
            "content": "Navigation icons powered by Lucide — lightweight open-source SVGs",
            "type": "info",
            "dismissable": True,
        },
        "sections": [
            {"title": "Tutorials", "dir": "tutorials"},
        ],
        "nav_icons": {
            "navbar": {
                "User Guide": "book-open",
                "Tutorials": "lightbulb",
                "Recipes": "chef-hat",
                "Reference": "code-2",
            },
            "sidebar": {
                # User Guide items
                "Getting Started": "rocket",
                "Configuration": "settings",
                "Visualization": "chart-line",
                "Advanced Topics": "graduation-cap",
                # Reference section headers
                "Functions": "zap",
                "Classes": "blocks",
                # Tutorials section headers (with icons)
                "Basics": "book",
                "Advanced": "trophy",
                # Tutorials items — only every other item gets an icon
                "Fundamentals": "compass",
                # "Data Loading" intentionally has NO icon
                "Pipelines": "git-branch",
                # "Chart Basics" intentionally has NO icon
                "Exporting": "download",
                # "Summary Reports" intentionally has NO icon
            },
        },
    },
    "files": {
        "gdtest_nav_icons/__init__.py": '''\
            """NavIcons Demo — a data-analysis toolkit showcasing navigation icons."""

            __version__ = "1.0.0"

            from .analysis import Pipeline, analyze, summarize, transform
            from .charts import BarChart, LineChart, plot
            from .io import load_csv, save_csv, export_json

            __all__ = [
                "Pipeline",
                "analyze",
                "summarize",
                "transform",
                "BarChart",
                "LineChart",
                "plot",
                "load_csv",
                "save_csv",
                "export_json",
            ]
        ''',
        "gdtest_nav_icons/analysis.py": '''\
            """Data analysis utilities."""


            def analyze(data: list[float]) -> dict[str, float]:
                """Run a basic statistical analysis on numeric data.

                Args:
                    data: A list of numeric values to analyze.

                Returns:
                    A dict with keys ``mean``, ``min``, ``max``, and ``count``.

                Examples:
                    >>> analyze([1.0, 2.0, 3.0])
                    {'mean': 2.0, 'min': 1.0, 'max': 3.0, 'count': 3}
                """
                return {
                    "mean": sum(data) / len(data),
                    "min": min(data),
                    "max": max(data),
                    "count": len(data),
                }


            def summarize(data: list[float], label: str = "result") -> str:
                """Produce a one-line summary string for a dataset.

                Args:
                    data: Numeric values.
                    label: Human-readable label for the summary.

                Returns:
                    A formatted summary string.
                """
                stats = analyze(data)
                return f"{label}: mean={stats['mean']:.2f}, n={stats['count']}"


            def transform(data: list[float], *, scale: float = 1.0, offset: float = 0.0) -> list[float]:
                """Apply a linear transform to every element.

                Args:
                    data: Input values.
                    scale: Multiplicative factor.
                    offset: Additive constant applied after scaling.

                Returns:
                    A new list of transformed values.
                """
                return [x * scale + offset for x in data]


            class Pipeline:
                """An ordered sequence of analysis stages.

                Construct a pipeline from callables, then run data through
                each stage in sequence.

                Args:
                    name: Human-readable pipeline identifier.

                Attributes:
                    name: Pipeline name.
                    stages: Ordered list of stage callables.

                Examples:
                    >>> p = Pipeline("demo")
                    >>> p.add_stage(lambda x: [v * 2 for v in x])
                    >>> p.run([1, 2, 3])
                    [2, 4, 6]
                """

                def __init__(self, name: str):
                    self.name = name
                    self.stages: list = []

                def add_stage(self, fn) -> None:
                    """Append a processing stage.

                    Args:
                        fn: A callable that accepts and returns a list.
                    """
                    self.stages.append(fn)

                def run(self, data: list) -> list:
                    """Execute all stages sequentially.

                    Args:
                        data: Input data list.

                    Returns:
                        The data after passing through every stage.
                    """
                    for fn in self.stages:
                        data = fn(data)
                    return data

                def clear(self) -> None:
                    """Remove all stages from the pipeline."""
                    self.stages.clear()

                def __len__(self) -> int:
                    return len(self.stages)

                def __repr__(self) -> str:
                    return f"Pipeline({self.name!r}, stages={len(self)})"
        ''',
        "gdtest_nav_icons/charts.py": '''\
            """Chart rendering utilities."""

            from __future__ import annotations


            class BarChart:
                """A horizontal bar chart renderer.

                Args:
                    title: Chart title displayed above the bars.
                    width: Maximum bar width in characters.

                Attributes:
                    title: Chart title.
                    width: Bar width cap.
                    data: Mapping of labels to values.
                """

                def __init__(self, title: str = "Chart", width: int = 40):
                    self.title = title
                    self.width = width
                    self.data: dict[str, float] = {}

                def add(self, label: str, value: float) -> None:
                    """Add a data point to the chart.

                    Args:
                        label: Bar label.
                        value: Numeric value.
                    """
                    self.data[label] = value

                def render(self) -> str:
                    """Render the chart as a text string.

                    Returns:
                        Multi-line string with the rendered bar chart.
                    """
                    if not self.data:
                        return f"{self.title}\\n(no data)"
                    mx = max(self.data.values())
                    lines = [self.title, "=" * len(self.title)]
                    for label, val in self.data.items():
                        bar_len = int(val / mx * self.width) if mx else 0
                        lines.append(f"  {label:>10s} | {'█' * bar_len} {val}")
                    return "\\n".join(lines)


            class LineChart:
                """A simple line chart renderer.

                Args:
                    title: Chart title.
                    height: Vertical resolution in rows.

                Attributes:
                    title: Chart title.
                    height: Row count for rendering.
                    series: Stored data series.
                """

                def __init__(self, title: str = "Line", height: int = 10):
                    self.title = title
                    self.height = height
                    self.series: list[list[float]] = []

                def add_series(self, values: list[float]) -> None:
                    """Add a data series.

                    Args:
                        values: Y-axis values for the series.
                    """
                    self.series.append(values)

                def render(self) -> str:
                    """Render the chart as text.

                    Returns:
                        Multi-line text representation.
                    """
                    return f"{self.title} ({len(self.series)} series)"


            def plot(x: list[float], y: list[float], *, kind: str = "scatter") -> str:
                """Produce a quick text-based plot.

                Args:
                    x: X-axis values.
                    y: Y-axis values.
                    kind: Plot type — ``"scatter"`` or ``"line"``.

                Returns:
                    A string representation of the plot.

                Raises:
                    ValueError: If ``x`` and ``y`` have different lengths.
                """
                if len(x) != len(y):
                    raise ValueError("x and y must have the same length")
                return f"{kind} plot with {len(x)} points"
        ''',
        "gdtest_nav_icons/io.py": '''\
            """Data I/O helpers."""

            from __future__ import annotations


            def load_csv(path: str, *, delimiter: str = ",", header: bool = True) -> list[dict]:
                """Load a CSV file into a list of row dicts.

                Args:
                    path: File path to read.
                    delimiter: Column separator character.
                    header: Whether the first row contains column names.

                Returns:
                    A list of dicts, one per data row.
                """
                return [{"_path": path, "_delim": delimiter, "_header": header}]


            def save_csv(data: list[dict], path: str, *, delimiter: str = ",") -> None:
                """Save a list of row dicts to a CSV file.

                Args:
                    data: Rows to write.
                    path: Destination file path.
                    delimiter: Column separator character.
                """
                pass


            def export_json(data: list[dict], path: str, *, indent: int = 2) -> None:
                """Export data as a formatted JSON file.

                Args:
                    data: Data to serialize.
                    path: Destination file path.
                    indent: Number of spaces for pretty-printing.
                """
                pass
        ''',
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            # Getting Started

            Welcome to **NavIcons Demo** — a data-analysis toolkit that
            showcases Lucide navigation icons in every corner of the site.

            ## Installation

            ```bash
            pip install gdtest-nav-icons
            ```

            ## Quick Example

            ```python
            from gdtest_nav_icons import analyze

            result = analyze([10, 20, 30, 40])
            print(result)
            # {'mean': 25.0, 'min': 10, 'max': 40, 'count': 4}
            ```

            ## What's Next?

            - Learn about [Configuration](configuration.qmd) options
            - Explore the [Visualization](visualization.qmd) guide
            - Dive into [Advanced Topics](advanced-topics.qmd)
        """,
        "user_guide/02-configuration.qmd": """\
            ---
            title: Configuration
            ---

            # Configuration

            Configure NavIcons Demo through Python or YAML.

            ## Pipeline Setup

            ```python
            from gdtest_nav_icons import Pipeline, transform

            pipe = Pipeline("preprocess")
            pipe.add_stage(lambda data: transform(data, scale=2.0))
            pipe.add_stage(lambda data: transform(data, offset=-1.0))

            result = pipe.run([1.0, 2.0, 3.0])
            ```

            ## CSV Options

            Use `load_csv` with custom delimiters:

            ```python
            from gdtest_nav_icons import load_csv

            data = load_csv("data.tsv", delimiter="\\t")
            ```
        """,
        "user_guide/03-visualization.qmd": """\
            ---
            title: Visualization
            ---

            # Visualization

            Create quick text-based charts for terminal output.

            ## Bar Charts

            ```python
            from gdtest_nav_icons import BarChart

            chart = BarChart("Sales by Region")
            chart.add("North", 120)
            chart.add("South", 85)
            chart.add("East", 200)
            chart.add("West", 150)
            print(chart.render())
            ```

            ## Line Charts

            ```python
            from gdtest_nav_icons import LineChart

            lc = LineChart("Temperature")
            lc.add_series([20, 22, 19, 25, 28, 26])
            print(lc.render())
            ```

            ## Quick Plots

            ```python
            from gdtest_nav_icons import plot

            output = plot([1, 2, 3, 4], [10, 20, 15, 30], kind="line")
            print(output)
            ```
        """,
        "user_guide/04-advanced-topics.qmd": """\
            ---
            title: Advanced Topics
            ---

            # Advanced Topics

            ## Custom Pipeline Stages

            Build complex analysis workflows by chaining stages:

            ```python
            from gdtest_nav_icons import Pipeline, analyze, summarize

            pipe = Pipeline("full-analysis")
            pipe.add_stage(lambda d: [x for x in d if x > 0])  # filter
            pipe.add_stage(lambda d: [x ** 0.5 for x in d])    # sqrt

            clean_data = pipe.run([-1, 4, 9, -2, 16, 25])
            print(analyze(clean_data))
            ```

            ## Exporting Results

            ```python
            from gdtest_nav_icons import export_json

            results = [{"metric": "accuracy", "value": 0.95}]
            export_json(results, "output.json", indent=4)
            ```

            ## Summary Reports

            ```python
            from gdtest_nav_icons import summarize

            print(summarize([88, 92, 79, 95, 100], label="Exam scores"))
            ```
        """,
        "recipes/01-quick-analysis.qmd": """\
            ---
            title: Quick Analysis
            ---

            # Quick Analysis Recipe

            Run a full analysis in three lines:

            ```python
            from gdtest_nav_icons import load_csv, analyze

            data = load_csv("measurements.csv")
            stats = analyze([row["value"] for row in data])
            ```
        """,
        "recipes/02-batch-export.qmd": """\
            ---
            title: Batch Export
            ---

            # Batch Export Recipe

            Export multiple datasets at once:

            ```python
            from gdtest_nav_icons import save_csv, export_json

            datasets = {"train": [...], "test": [...]}
            for name, rows in datasets.items():
                save_csv(rows, f"{name}.csv")
                export_json(rows, f"{name}.json")
            ```
        """,
        "recipes/03-chart-dashboard.qmd": """\
            ---
            title: Chart Dashboard
            ---

            # Chart Dashboard Recipe

            Build a simple terminal dashboard:

            ```python
            from gdtest_nav_icons import BarChart, LineChart

            bar = BarChart("Revenue")
            bar.add("Q1", 100)
            bar.add("Q2", 130)
            bar.add("Q3", 115)
            bar.add("Q4", 160)

            line = LineChart("Growth")
            line.add_series([100, 130, 115, 160])

            print(bar.render())
            print()
            print(line.render())
            ```
        """,
        "README.md": """\
            # NavIcons Demo

            A data-analysis toolkit that showcases **Lucide navigation icons**
            on both the navbar and sidebar. Every major navigation entry —
            User Guide, Tutorials, Recipes, Reference, and sidebar section
            headers — is prefixed with an inline SVG icon for quick visual
            scanning. The Tutorials section deliberately uses incomplete
            icon coverage to verify icons work when only some items have them.

            ## Features

            - **Statistical analysis**: `analyze()`, `summarize()`, `transform()`
            - **Charting**: `BarChart`, `LineChart`, `plot()`
            - **I/O**: `load_csv()`, `save_csv()`, `export_json()`
            - **Pipelines**: `Pipeline` for composable data workflows

            ## Quick Start

            ```python
            from gdtest_nav_icons import analyze

            print(analyze([1, 2, 3, 4, 5]))
            ```
        """,
        # ── Tutorials section: 6 pages in 2 subsection groups ──
        "tutorials/basics/01-fundamentals.qmd": """\
            ---
            title: Fundamentals
            ---

            # Fundamentals

            Learn the core concepts behind data analysis with NavIcons Demo.

            ## Data Types

            All analysis functions work with `list[float]` inputs:

            ```python
            from gdtest_nav_icons import analyze

            analyze([1.0, 2.0, 3.0])
            ```

            ## Return Types

            Results are always plain Python dicts or strings — no custom types.
        """,
        "tutorials/basics/02-data-loading.qmd": """\
            ---
            title: Data Loading
            ---

            # Data Loading

            Load data from CSV files into Python data structures.

            ```python
            from gdtest_nav_icons import load_csv

            rows = load_csv("data.csv")
            values = [row["value"] for row in rows]
            ```

            ## Delimiter Options

            Use ``delimiter`` for TSV or other formats:

            ```python
            rows = load_csv("data.tsv", delimiter="\\t")
            ```
        """,
        "tutorials/basics/03-pipelines.qmd": """\
            ---
            title: Pipelines
            ---

            # Pipelines

            Build composable processing workflows with the Pipeline class.

            ```python
            from gdtest_nav_icons import Pipeline, transform

            pipe = Pipeline("clean")
            pipe.add_stage(lambda d: [x for x in d if x > 0])
            pipe.add_stage(lambda d: transform(d, scale=0.01))
            result = pipe.run([-5, 10, 20, -3, 15])
            ```

            ## Pipeline Inspection

            ```python
            len(pipe)   # number of stages
            repr(pipe)  # Pipeline('clean', stages=2)
            ```
        """,
        "tutorials/advanced/01-chart-basics.qmd": """\
            ---
            title: Chart Basics
            ---

            # Chart Basics

            Quick introduction to text-based charting.

            ## Creating a Bar Chart

            ```python
            from gdtest_nav_icons import BarChart

            chart = BarChart("Scores")
            chart.add("Alice", 95)
            chart.add("Bob", 87)
            print(chart.render())
            ```

            ## Creating a Line Chart

            ```python
            from gdtest_nav_icons import LineChart

            lc = LineChart("Trend")
            lc.add_series([10, 15, 12, 18])
            print(lc.render())
            ```
        """,
        "tutorials/advanced/02-exporting.qmd": """\
            ---
            title: Exporting
            ---

            # Exporting

            Save processed data to disk in various formats.

            ## CSV Export

            ```python
            from gdtest_nav_icons import save_csv

            save_csv([{"name": "Alice", "score": 95}], "results.csv")
            ```

            ## JSON Export

            ```python
            from gdtest_nav_icons import export_json

            export_json([{"metric": "accuracy", "value": 0.92}], "metrics.json")
            ```
        """,
        "tutorials/advanced/03-summary-reports.qmd": """\
            ---
            title: Summary Reports
            ---

            # Summary Reports

            Generate human-readable summaries of datasets.

            ```python
            from gdtest_nav_icons import summarize

            print(summarize([88, 92, 79, 95, 100], label="Exam scores"))
            # Exam scores: mean=90.80, n=5
            ```

            ## Custom Labels

            The ``label`` parameter controls the prefix in the output string.
        """,
    },
    "expected": {
        "detected_name": "gdtest-nav-icons",
        "detected_module": "gdtest_nav_icons",
        "detected_parser": "google",
        "export_names": [
            "Pipeline",
            "analyze",
            "summarize",
            "transform",
            "BarChart",
            "LineChart",
            "plot",
            "load_csv",
            "save_csv",
            "export_json",
        ],
        "num_exports": 10,
        "section_titles": ["Functions", "Classes"],
        "has_user_guide": True,
        "has_recipes": True,
        "has_tutorials": True,
    },
}
