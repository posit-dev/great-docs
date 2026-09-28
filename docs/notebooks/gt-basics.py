# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     # great-tables >= 0.22 depends on multimark, a compiled package with no
#     # pure-Python / WASM wheel, so it can't install under Pyodide. Pin to the
#     # last pure-Python release (0.21.x) so the notebook runs in the browser.
#     "great-tables<0.22",
#     "polars",
# ]
# ///

import marimo

app = marimo.App()


@app.cell
def __():
    import marimo as mo

    return (mo,)


@app.cell
async def __():
    import sys

    if "pyodide" in sys.modules:
        import micropip

        await micropip.install(["great-tables<0.22", "polars"])

    import great_tables as gt
    import polars as pl

    return gt, pl


@app.cell
def __(mo):
    mo.md(
        """
        # Getting Started with Great Tables

        This notebook builds a styled table with **Great Tables**. Drag the
        slider below — the table redraws reactively as the value changes.
        """
    )
    return


@app.cell
def __(pl):
    # The full dataset — a slider chooses how many rows to show.
    students = pl.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "Diana", "Evan", "Fiona", "Grace", "Hugo"],
            "score": [95, 87, 92, 88, 79, 96, 84, 91],
            "grade": ["A", "B+", "A-", "B+", "C+", "A", "B", "A-"],
        }
    )
    return (students,)


@app.cell
def __(mo):
    top_n = mo.ui.slider(1, 8, value=4, label="Show top N students")
    top_n
    return (top_n,)


@app.cell
def __(gt, students, top_n):
    # Reactive: re-runs whenever the slider moves.
    df = students.sort("score", descending=True).head(top_n.value)

    (
        gt.GT(df)
        .tab_header(
            title="Student Scores",
            subtitle=f"Top {top_n.value} of {students.height}, Fall 2026",
        )
        .cols_label(
            name="Student",
            score="Score",
            grade="Grade",
        )
        .data_color(
            columns="score",
            palette=["#fde725", "#21918c"],
        )
    )
    return (df,)


@app.cell
def __(mo):
    mo.md(
        """
        Every cell that depends on the slider re-runs the moment its value
        changes — no "Run" button required. In iframe mode you can also edit
        the code above and re-run it live.
        """
    )
    return


if __name__ == "__main__":
    app.run()
