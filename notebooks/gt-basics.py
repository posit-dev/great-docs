# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "great-tables",
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

        await micropip.install(["great-tables", "polars"])

    _packages_ready = True
    return (_packages_ready,)


@app.cell
def __(mo):
    mo.md(
        """
        # Getting Started with Great Tables

        This notebook demonstrates the basics of creating tables with **Great Tables**.
        Edit the code below and see the output update reactively!
        """
    )
    return


@app.cell
def __(_packages_ready):
    import great_tables as gt
    import polars as pl

    return gt, pl


@app.cell
def __(gt, pl):
    # Create sample data
    df = pl.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie", "Diana"],
            "score": [95, 87, 92, 88],
            "grade": ["A", "B+", "A-", "B+"],
        }
    )

    # Build a Great Table
    (
        gt.GT(df)
        .tab_header(
            title="Student Scores",
            subtitle="Fall 2026 Semester",
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
    return df


@app.cell
def __(mo):
    mo.md(
        """
        Try modifying the data or the table styling above —
        the output will update automatically thanks to marimo's reactive execution.
        """
    )
    return


if __name__ == "__main__":
    app.run()
